"""
Load the NU master school list (Bob's College-Board-style org export) into
PostgreSQL — see data/NU-Master/README.md for what this file is and why it
matters (the CEEB-anchored master list build_ceeb_crosswalk.py needs).

Table created:
  nu_master_org_data — one row per org (PK: guid). CEEB is the shared join
  key against schools_combined_enriched_ceeb (see load_schools_ceeb.py) and
  against NCES/IB/ISBE/CPS via build_ceeb_crosswalk.py.
"""

import re
import pandas as pd
from sqlalchemy import create_engine, text
from config import DATABASE_URL, NU_MASTER_PATH
import db_utils

# Pure section-divider columns in the source export — same literal string
# repeated on every row, no information content.
DIVIDER_COLUMNS = ["----", "--Org Details--", "--Org Details--School Profile Info--"]


def _normalize_col(c: str) -> str:
    c = c.strip().replace("%", "pct").replace("#", "num")
    c = re.sub(r"[^A-Za-z0-9]+", "_", c)
    return re.sub(r"_+", "_", c).strip("_").lower()


def load_nu_master(engine):
    print(f"Reading NU master org data from {NU_MASTER_PATH}...")
    # CEEB/GUID as text — numeric inference would drop CEEB's leading zeros
    # (e.g. "010370" -> 10370), breaking the exact-match join in combine_schools.py.
    df = pd.read_excel(NU_MASTER_PATH, sheet_name="Export", dtype={"CEEB": str, "GUID": str})
    df = df.drop(columns=[c for c in DIVIDER_COLUMNS if c in df.columns])
    df.columns = [_normalize_col(c) for c in df.columns]

    print(f"  {len(df):,} rows, {len(df.columns)} columns")
    df.to_sql("nu_master_org_data", engine, if_exists="replace", index=False,
              method=db_utils.psql_insert_copy)
    print("  Loaded nu_master_org_data ✓")

    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE nu_master_org_data ADD PRIMARY KEY (guid)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_nu_master_org_data_ceeb ON nu_master_org_data (ceeb)"))
        conn.commit()


if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    load_nu_master(engine)
