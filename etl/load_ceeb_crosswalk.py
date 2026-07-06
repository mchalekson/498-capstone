"""
Load the UC Boulder NCES<->CEEB crosswalk (third-party, external source —
see data/CEEB-Crosswalk/README.md for provenance, license, and caveats).

Table created:
  nces_ceeb_crosswalk_source — one row per (school, CEEB) pair as published
  upstream. Not deduplicated here (78 NCES IDs and 6 CEEB codes repeat in
  the source) and no PK, since this is the raw external file as-is.
"""

import os
import pandas as pd
from sqlalchemy import create_engine
from config import DATABASE_URL, DATA_DIR
import db_utils


def load_ceeb_crosswalk(engine):
    path = os.path.join(DATA_DIR, "CEEB-Crosswalk", "oda_nces_ceeb_crosswalk.csv")
    print("Reading NCES<->CEEB crosswalk (UC Boulder, external source)...")
    df = pd.read_csv(path, dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]

    print(f"  {len(df):,} rows, {len(df.columns)} columns")
    df.to_sql("nces_ceeb_crosswalk_source", engine, if_exists="replace", index=False,
              method=db_utils.psql_insert_copy)
    print("  Loaded nces_ceeb_crosswalk_source ✓")


if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    load_ceeb_crosswalk(engine)
