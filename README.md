# 498-capstone

ETL pipeline that loads NCES, Census, NAEP, ISBE, IB, CPS, and College Board
data into a Postgres database and combines it into school-level enriched
tables.

## Quickstart

Every table and view is already exported to CSV in [`csv_exports/`](csv_exports/) —
for most work (feature engineering, rigor classification, clustering, benchmarking)
you don't need Docker or Postgres at all, just the CSVs already in this repo.

To rebuild everything from raw sources instead:

```
docker-compose up
```

Or without Docker, point `etl/config.py` at a running Postgres instance and
run `python etl/run_all.py` from `etl/`.

**Requires raw source data that isn't in this repo.** `data/updated-sheng/`
(Sheng's combined schools export, Bob's NU org export, and the raw CRDC/EDFacts
assessment data) is gitignored — it's ~2.6 GB, well past what's reasonable to
version in git (a single CRDC file alone is 794 MB, and two EDFacts files are
938 MB and 875 MB, over GitHub's 100 MB per-file limit on their own). Get it
from the team's shared Drive folder:
[data (Google Drive)](https://drive.google.com/drive/folders/1H0_L1gA-ND8acU7Ux1VC9PIDyH0svpJ9?usp=sharing) —
request access from Max if you can't see it. Download it into `data/updated-sheng/`
before running `docker-compose up` or `etl/run_all.py`.

`tests/test_docker_pipeline.py` auto-skips if this data isn't present locally,
so the test suite still runs (see [`docs/TEST_PLAN.md`](docs/TEST_PLAN.md))
without it.

## The finalized dataset

The project's terminal artifact is
**`csv_exports/modeling_dataset_v1_2026-07-17.csv`** — 34,392 US high schools
(public + private, grades 9–12 enrollment ≥ 30) × 57 variables, keyed on `ceeb`.
Every number in the report's Section 4 is computed from it. Its companion
dictionary is `csv_exports/data_dictionary_modeling_dataset.csv` (one row per
variable: source, grain, vintage, confidence, range, % non-null, description).

Note there are **two** dictionaries, describing different tables:

| Dictionary | Describes | Size |
|---|---|---|
| `docs/DATA_DICTIONARY.md` + `docs/data_dictionary_schools_org_enriched.csv` | the raw joined table (`schools_org_enriched`) | 127 variables |
| `csv_exports/data_dictionary_modeling_dataset.csv` | the frozen modeling dataset | 57 variables |

### How it's built

Stages 1–5 (`run_all.py`) end at `schools_org_enriched` / `schools_org_all`.
The modeling layer is a separate chain of CSV-in/CSV-out scripts on top of that:

```
schools_org_all.csv               (stage 3 output)
  → build_features.py             → schools_features.csv
  → build_modeling_dataset.py     → modeling_dataset_<ver>_<date>.csv + its dictionary
  → build_rigor_classification.py → rigor_classification_… + rigor_sensitivity_…
      ├─ build_clustering.py      → clustering_… + pca_loadings_… + gap_statistic_…
      └─ build_benchmarking.py    → benchmarking_…
```

Run that whole chain in order with:

```
cd etl/ && python run_modeling_layer.py --dry-run   # print the sequence first
cd etl/ && python run_modeling_layer.py
```

**This is deliberately not part of `run_all.py`.** Each build script stamps its
output with the current date, so running them on every pipeline run would mint a
new dataset each time rather than reproducing the frozen one.

`etl/load_modeling_layer.py` therefore pins an **exact** freeze tag
(`FREEZE_TAG = "v1_2026-07-17"`) — version *and* date — and resolves it by exact
filename match with no "newest wins" fallback. Pinning on the version alone isn't
a pin: any rebuild at the same version outranks the freeze just by being newer,
whether or not it was meant to replace it.

Promoting a new build to the freeze is an explicit two-step act:

```
cd etl/ && python run_modeling_layer.py --version v2   # writes v2_<today> artifacts
# then set FREEZE_TAG = "v2_<date>" in etl/load_modeling_layer.py
```

Stray non-freeze artifacts are reported (not loaded) on every stage-6 run. They're
safe to delete; only the pinned tag is committed.

### Querying it in Postgres

Stage 6 of `run_all.py` loads the frozen modeling layer into Postgres, so these
are queryable and joinable alongside the rest of the pipeline:

`modeling_dataset`, `rigor_classification`, `clustering`, `benchmarking`,
`rigor_sensitivity`, `pca_loadings`, `gap_statistic`,
`data_dictionary_modeling_dataset`, and `modeling_layer_manifest` (records which
frozen file each table was loaded from).

The four school-level tables are all the same 34,392 rows — each is the previous
one plus appended columns. They're kept separate rather than flattened into one
wide table so a disagreement between build stages stays visible. `ceeb` is unique
where present but NULL for ~5,400 rows, so it's indexed, not a primary key.

To load them without a full pipeline run: `cd etl/ && python load_modeling_layer.py`.
The stage skips with a message if the freeze isn't on disk, so a clone that has
only run stages 1–5 won't fail.

## Docs

- [`docs/EDA.md`](docs/EDA.md) — source inventory, join keys, profiling
- [`docs/EDA_NCES_private_EN.md`](docs/EDA_NCES_private_EN.md) — NCES private-school EDA
- [`docs/BOB_BRIEFING.md`](docs/BOB_BRIEFING.md) — database overview and open data gaps
- [`data/NU-Master/README.md`](data/NU-Master/README.md) — what's needed for the CEEB crosswalk
