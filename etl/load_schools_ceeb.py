"""
Load Sheng's nationwide schools export into PostgreSQL. This is a
combined public+private school table, already enriched with a CEEB column
via the UC Boulder crosswalk (data/CEEB-Crosswalk/README.md) — a separate,
already-built stand-in for what the project's own
nces_public_ceeb_crosswalk / nces_private_ceeb_crosswalk tables
(build_ceeb_crosswalk.py) will eventually produce.

Table created:
  schools_combined_enriched_ceeb — one row per school (PK: school_id).
  ceeb is nullable and not unique (~1,400 CEEB codes cover >1 row — see
  ceeb_match_tier/ceeb_needs_review for match confidence per row).
"""

import pandas as pd
from sqlalchemy import create_engine, text
from config import DATABASE_URL, SCHOOLS_CEEB_PATH
import db_utils

# Zero-padded ID columns — read as text or pandas' numeric inference
# silently drops the leading zero (e.g. ceeb "010370" -> 10370.0), which
# would break the exact-match CEEB join in combine_schools.py.
ID_COLUMNS = ["school_id", "nces_id_7", "nces_id_12", "pss_id", "ceeb",
              "leaid", "rcdts", "county_fips"]


def load_schools_ceeb(engine):
    print(f"Reading schools+CEEB export from {SCHOOLS_CEEB_PATH}...")
    df = pd.read_csv(SCHOOLS_CEEB_PATH, dtype={c: str for c in ID_COLUMNS}, low_memory=False)

    print(f"  {len(df):,} rows, {len(df.columns)} columns")
    df.to_sql("schools_combined_enriched_ceeb", engine, if_exists="replace", index=False,
              method=db_utils.psql_insert_copy)
    print("  Loaded schools_combined_enriched_ceeb ✓")

    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE schools_combined_enriched_ceeb ADD PRIMARY KEY (school_id)"))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_schools_combined_enriched_ceeb_ceeb "
            "ON schools_combined_enriched_ceeb (ceeb)"
        ))
        conn.commit()


if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    load_schools_ceeb(engine)
