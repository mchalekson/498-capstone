"""
Run the full ETL pipeline in order:
  1. Load raw data into raw_* tables
  2. Clean and produce *_clean tables
  3. Apply SQL views for analysis
  4. Load the frozen modeling layer into Postgres

Note on stage 6: this LOADS the already-frozen modeling-layer CSVs, it does not
rebuild them. The build scripts stamp their outputs with the current date, so
rebuilding them here would mint a new dataset on every pipeline run instead of
reproducing the frozen one. Rebuilding is a separate, deliberate step:
  python run_modeling_layer.py

Usage:
  cd etl/
  python run_all.py

Set DB credentials via environment variables before running:
  export DB_HOST=localhost
  export DB_NAME=capstone
  export DB_USER=postgres
  export DB_PASS=yourpassword
"""

import os
import sys
import traceback
from sqlalchemy import create_engine, text
from config import DATABASE_URL

import load_nces
import load_census
import load_naep
import load_collegeboard
import load_ib
import load_isbe
import load_cps
import load_ceeb_crosswalk
import load_nu_master
import load_schools_ceeb

import clean_nces
import clean_census
import clean_naep
import clean_isbe

import combine_schools
import build_ceeb_crosswalk
import load_modeling_layer

STEPS = [
    # ── Stage 1: Raw loads ──────────────────────────────────────────────
    ("Load NCES public schools",    load_nces.load_public),
    ("Load NCES private schools",   load_nces.load_private),
    ("Load NCES public HS (9-12)",  load_nces.load_public_hs912),
    ("Load NCES private merged",    load_nces.load_private_merged),
    ("Load Census finances",        load_census.load_finances),
    ("Load Census SAIPE poverty",   load_census.load_saipe),
    ("Load NAEP assessments",       load_naep.load_naep),
    ("Load College Board AP",       load_collegeboard.load_collegeboard),
    ("Load IB schools",             load_ib.load_ib),
    ("Load ISBE report card",       load_isbe.load_isbe),
    ("Load CPS opportunity index",  load_cps.load_cps),
    ("Load NCES-CEEB crosswalk source", load_ceeb_crosswalk.load_ceeb_crosswalk),
    ("Load NU master org data",     load_nu_master.load_nu_master),
    ("Load schools+CEEB export",    load_schools_ceeb.load_schools_ceeb),

    # ── Stage 2: Clean ──────────────────────────────────────────────────
    ("Clean NCES public schools",   clean_nces.clean_public),
    ("Clean NCES private schools",  clean_nces.clean_private),
    ("Clean NCES private merged",   clean_nces.clean_private_merged),
    ("Clean Census finances",       clean_census.clean_finances),
    ("Clean Census SAIPE poverty",  clean_census.clean_saipe),
    ("Clean NAEP assessments",      clean_naep.clean_naep),
    ("Clean ISBE report card",      clean_isbe.clean_isbe),

    # ── Stage 3: Combine ─────────────────────────────────────────────────
    ("Combine public schools (nationwide)",  combine_schools.build_public_schools_enriched),
    ("Combine private schools (nationwide)", combine_schools.build_private_schools_enriched),
    ("Combine CPS-NCES crosswalk",           combine_schools.build_cps_nces_crosswalk),
    ("Combine schools + NU org data on CEEB", combine_schools.build_schools_org_enriched),
    ("Combine schools + NU org data, outer join (all rows)", combine_schools.build_schools_org_all),

    # ── Stage 4: CEEB junction ────────────────────────────────────────────
    ("Build NCES<->CEEB junction",           build_ceeb_crosswalk.build_nces_junction),

    # ── Stage 5: NU-master CEEB crosswalk (optional — no-ops until it exists) ──
    ("Build CEEB crosswalk (IB/ISBE/CPS)",   build_ceeb_crosswalk.build_all),

    # ── Stage 6: Modeling layer (optional — skips if the freeze isn't present) ──
    ("Load frozen modeling layer",           load_modeling_layer.load_modeling_layer),
]


def drop_views(engine):
    # Re-running the pipeline against an already-loaded database otherwise
    # fails: to_sql(if_exists="replace") issues DROP TABLE, and Postgres
    # refuses to drop a table these views depend on. Views are recreated
    # by apply_views() at the end of the run.
    with engine.connect() as conn:
        conn.execute(text(
            "DROP VIEW IF EXISTS illinois_schools_enriched, districts_enriched, ib_nces_crosswalk"
        ))
        conn.commit()


def apply_views(engine):
    views_path = os.path.join(os.path.dirname(__file__), "views.sql")
    with open(views_path) as f:
        sql = f.read()
    with engine.connect() as conn:
        for statement in sql.split(";"):
            stmt = statement.strip()
            if stmt:
                conn.execute(text(stmt))
        conn.commit()
    print("  SQL views applied ✓")


def main():
    engine = create_engine(DATABASE_URL)
    failed = []

    drop_views(engine)

    for name, fn in STEPS:
        if name == "Load frozen modeling layer":
            stage = "MODELING"
        elif name.startswith("Load"):
            stage = "LOAD"
        elif name.startswith("Combine"):
            stage = "COMBINE"
        else:
            stage = "CLEAN"
        print(f"\n{'='*50}")
        print(f"[{stage}] {name}")
        print("=" * 50)
        try:
            fn(engine)
        except Exception as e:
            print(f"  ERROR: {e}")
            traceback.print_exc()
            failed.append(name)

    print(f"\n{'='*50}")
    print("[VIEWS] Applying SQL analytical views")
    print("=" * 50)
    try:
        apply_views(engine)
    except Exception as e:
        print(f"  ERROR applying views: {e}")
        traceback.print_exc()
        failed.append("SQL views")

    print(f"\n{'='*50}")
    if failed:
        print(f"Pipeline completed with errors in:\n  " + "\n  ".join(failed))
        sys.exit(1)
    else:
        print("Pipeline completed successfully ✓")
        print("\nTables available:")
        print("  Raw:   nces_public_schools, nces_private_schools, nces_public_hs_grades_9_12,")
        print("         nces_private_merged, census_school_finances, census_saipe_poverty,")
        print("         naep_assessments, ap_availability, ap_participation, ap_performance,")
        print("         ib_schools, isbe_*, cps_opportunity_index, nu_master_org_data,")
        print("         schools_combined_enriched_ceeb")
        print("  Clean: nces_public_schools_clean, nces_private_schools_clean,")
        print("         nces_private_merged_clean, census_school_finances_clean,")
        print("         census_saipe_poverty_clean, naep_assessments_clean, isbe_*_clean")
        print("  Combined: public_schools_enriched, private_schools_enriched, cps_nces_crosswalk,")
        print("         schools_org_enriched, schools_org_all")
        print("  Views: illinois_schools_enriched, districts_enriched, ib_nces_crosswalk")
        print("  NCES<->CEEB junction: nces_public_ceeb_crosswalk, nces_private_ceeb_crosswalk")
        print("  CEEB crosswalk (NU master):")
        print("         ib_ceeb_crosswalk, isbe_ceeb_crosswalk, cps_ceeb_crosswalk")
        print("  Modeling layer (frozen freeze, see modeling_layer_manifest for which")
        print("         file each came from): modeling_dataset, rigor_classification,")
        print("         clustering, benchmarking, rigor_sensitivity, pca_loadings,")
        print("         gap_statistic, data_dictionary_modeling_dataset")


if __name__ == "__main__":
    main()
