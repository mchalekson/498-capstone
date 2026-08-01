"""
Load the modeling-layer artifacts into PostgreSQL (pipeline stage 6).

Why this exists
---------------
Stages 1-5 of run_all.py end at `schools_org_enriched` / `schools_org_all`.
Everything after that -- build_features.py -> build_modeling_dataset.py ->
build_rigor_classification.py -> {build_clustering.py, build_benchmarking.py}
-- is CSV-in/CSV-out and never touched the database. That left the project's
actual terminal artifact (the frozen modeling dataset) as a file with no table
behind it: `docker-compose up` rebuilt the database but not the dataset, and
nobody could query the thing the report's Section 4 is computed from.

This module closes that gap from the database side: it loads the already-built,
already-frozen modeling-layer CSVs into Postgres so they're queryable and
joinable against the rest of the pipeline.

What it deliberately does NOT do
--------------------------------
It does not re-run the build scripts. Those write date-tagged filenames
(`modeling_dataset_v1_<today>.csv`), so running them as part of run_all.py
would mint a NEW dataset on every pipeline run rather than reproducing the
frozen one -- which is the opposite of what "frozen, versioned dataset" means.
Rebuilding is an explicit, separate act: see run_modeling_layer.py.

So the contract here is: the CSVs in csv_exports/ are the source of truth for
the freeze, and this step mirrors them into the database as-is.

Tables created (stable names, no version suffix -- the version each one came
from is recorded in modeling_layer_manifest):

  modeling_dataset               the frozen feature set (report Section 4 input)
  rigor_classification           modeling_dataset + rigor score/tier columns
  clustering                     rigor_classification + PCA/cluster columns
  benchmarking                   rigor_classification + SAT percentile columns
  rigor_sensitivity              alternate-weighting-scheme comparison
  pca_loadings                   PCA component loadings by feature
  gap_statistic                  gap statistic by k
  data_dictionary_modeling_dataset   57-variable dictionary for modeling_dataset
  modeling_layer_manifest        which file each table above was loaded from

Note on grain: modeling_dataset, rigor_classification, clustering, and
benchmarking are all one row per school and all the same 34,392 rows -- each
later table is the earlier one plus appended columns. They are stored as
separate tables (rather than one wide table) to mirror the build steps, so a
disagreement between stages stays visible instead of being flattened away.
`ceeb` is unique where present but is NULL for ~5,400 rows, so it is indexed,
not made a primary key.
"""

import datetime as dt
import glob
import os

import pandas as pd
from sqlalchemy import create_engine, text

from config import DATABASE_URL
import db_utils

# Where the frozen modeling-layer CSVs live, relative to this file.
CSV_EXPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "csv_exports")

# The freeze this pipeline is pinned to -- the FULL tag, version *and* date, not
# just "v1".
#
# Pinning to a version and taking the newest match is not a pin, it's a moving
# target: any build re-run at the same version outranks the freeze purely by
# being newer, whether or not it was meant to replace it. That bit this project
# once already -- tests/test_system_pipeline.py used to run the real build chain
# inside csv_exports/, so `pytest tests/` alone minted `*_v1_<today>.csv` files
# that superseded the freeze, and it uses a narrower clustering sweep, so its
# output differed in substance and not just in date. That test now runs in a
# temp directory, but the exact-tag pin stays: it's the property that makes the
# freeze actually frozen, rather than a convention everyone has to remember.
#
# Bump this deliberately when a new freeze is cut, and say so in the docs.
FREEZE_TAG = "v4_2026-08-01"

# table name -> filename stem. Date-tagged files are resolved by glob against
# FREEZE_TAG; undated ones are matched literally.
DATED_ARTIFACTS = {
    "modeling_dataset": "modeling_dataset",
    "rigor_classification": "rigor_classification",
    "clustering": "clustering",
    "benchmarking": "benchmarking",
    "rigor_sensitivity": "rigor_sensitivity",
    "pca_loadings": "pca_loadings",
    "gap_statistic": "gap_statistic",
}

UNDATED_ARTIFACTS = {
    "data_dictionary_modeling_dataset": "data_dictionary_modeling_dataset.csv",
}

# Columns worth an index: the join keys people will actually filter/join on.
INDEX_COLUMNS = {
    "modeling_dataset": ["ceeb", "state", "sector"],
    "rigor_classification": ["ceeb", "rigor_tier_num"],
    "clustering": ["ceeb", "cluster_kmeans"],
    "benchmarking": ["ceeb", "funding_tier"],
}


def _resolve_dated(stem, tag=FREEZE_TAG, csv_dir=CSV_EXPORTS_DIR):
    """Resolve a date-tagged artifact by EXACT freeze tag.

    Exact-match only, by design: any "closest match" or "newest wins" fallback is
    how the freeze drifts without anyone noticing (see FREEZE_TAG). If the pinned
    file isn't there, that's a None the caller reports -- not something to paper
    over with a neighbouring file.
    """
    path = os.path.join(csv_dir, f"{stem}_{tag}.csv")
    return path if os.path.exists(path) else None


def resolve_artifacts(tag=FREEZE_TAG, csv_dir=CSV_EXPORTS_DIR):
    """Map table name -> resolved CSV path. Missing artifacts map to None."""
    resolved = {}
    for table, stem in DATED_ARTIFACTS.items():
        resolved[table] = _resolve_dated(stem, tag, csv_dir)
    for table, filename in UNDATED_ARTIFACTS.items():
        path = os.path.join(csv_dir, filename)
        resolved[table] = path if os.path.exists(path) else None
    return resolved


def find_stray_builds(tag=FREEZE_TAG, csv_dir=CSV_EXPORTS_DIR):
    """Date-tagged artifacts on disk that are NOT the pinned freeze.

    Usually the residue of a rebuild run without promoting it to the freeze.
    Harmless to the load itself now that resolution is exact, but worth surfacing
    so nobody mistakes a stray file for the frozen dataset.
    """
    stray = []
    for stem in DATED_ARTIFACTS.values():
        for path in sorted(glob.glob(os.path.join(csv_dir, f"{stem}_*.csv"))):
            if os.path.basename(path) != f"{stem}_{tag}.csv":
                stray.append(path)
    return stray


def _tidy(df, table):
    """Normalize a modeling-layer frame for Postgres.

    pca_loadings is written with the feature name as a nameless index column;
    everything else already has clean snake_case headers from the build scripts.
    """
    df = df.rename(columns={c: "feature" for c in df.columns if not str(c).strip()
                            or str(c).startswith("Unnamed:")})
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def _add_indexes(engine, table, df):
    for col in INDEX_COLUMNS.get(table, []):
        if col not in df.columns:
            continue
        with engine.connect() as conn:
            conn.execute(text(
                f'CREATE INDEX IF NOT EXISTS "idx_{table}_{col}" ON "{table}" ("{col}")'
            ))
            conn.commit()


def load_modeling_layer(engine, tag=FREEZE_TAG, csv_dir=CSV_EXPORTS_DIR):
    """Load every available modeling-layer artifact into Postgres.

    Missing artifacts are skipped with a message rather than raising: the
    modeling layer is built by hand today (see run_modeling_layer.py), so a
    fresh clone that has only ever run stages 1-5 legitimately won't have them,
    and that shouldn't fail the whole pipeline.
    """
    artifacts = resolve_artifacts(tag, csv_dir)
    manifest_rows = []
    loaded = 0

    stray = find_stray_builds(tag, csv_dir)
    if stray:
        print(f"  ! {len(stray)} date-tagged artifact(s) in {os.path.basename(csv_dir)}/ "
              f"are not the pinned freeze ({tag}) and are being ignored:")
        for path in stray[:8]:
            print(f"      {os.path.basename(path)}")
        if len(stray) > 8:
            print(f"      ... and {len(stray) - 8} more")
        print("    Likely an uncommitted rebuild. Promote one by setting FREEZE_TAG.")

    for table, path in artifacts.items():
        if path is None:
            print(f"  - {table}: not present at freeze {tag}, skipping")
            continue

        df = _tidy(pd.read_csv(path, low_memory=False), table)
        df.to_sql(table, engine, if_exists="replace", index=False,
                  method=db_utils.psql_insert_copy)
        _add_indexes(engine, table, df)
        loaded += 1
        print(f"  Loaded {table} ({len(df):,} rows x {df.shape[1]} cols) "
              f"from {os.path.basename(path)} ✓")

        manifest_rows.append({
            "table_name": table,
            "source_file": os.path.basename(path),
            "freeze_tag": tag,
            "n_rows": len(df),
            "n_columns": df.shape[1],
            "loaded_at": dt.datetime.now().isoformat(timespec="seconds"),
        })

    if not manifest_rows:
        print(f"  No modeling-layer artifacts found in {csv_dir} at freeze {tag}.")
        print("  Build them first:  python run_modeling_layer.py")
        return

    # The manifest is the point of this stage as much as the tables are: it's the
    # only place that records which frozen file each table came from, which is the
    # same provenance question the data dictionary's vintage column asks of the
    # upstream sources.
    pd.DataFrame(manifest_rows).to_sql(
        "modeling_layer_manifest", engine, if_exists="replace", index=False,
        method=db_utils.psql_insert_copy)
    print(f"  Loaded modeling_layer_manifest ({loaded} artifacts) ✓")


if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    load_modeling_layer(engine)
