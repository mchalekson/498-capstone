"""
Load US Census school finance and SAIPE poverty data into PostgreSQL.

Tables created:
  census_school_finances — district-level revenue/expenditure (PK: ncesid)
  census_saipe_poverty   — district-level poverty estimates (PK: state + distid)
"""

import os
import re
import pandas as pd
from sqlalchemy import create_engine, text
from config import DATABASE_URL, DATA_DIR


def clean_col(name: str) -> str:
    name = str(name).strip().lower()
    name = re.sub(r"[^\w]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name


def load_finances(engine):
    path = os.path.join(DATA_DIR, "US-Census", "census_school_finances_FY2024_alldistricts.xlsx")
    print("Reading Census school finances...")
    df = pd.read_excel(path)
    df.columns = [clean_col(c) for c in df.columns]

    # NCESID is the NCES district ID (LEAID)
    if "ncesid" in df.columns:
        df = df.rename(columns={"ncesid": "leaid"})

    print(f"  {len(df):,} rows, {len(df.columns)} columns")
    df.to_sql("census_school_finances", engine, if_exists="replace", index=False,
              method="multi", chunksize=500)
    print("  Loaded census_school_finances ✓")

    with engine.connect() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_finances_leaid ON census_school_finances (leaid)"))
        conn.commit()


def load_saipe(engine):
    path = os.path.join(DATA_DIR, "US-Census-Saipe", "census_saipe_poverty_2024_schooldistricts.xls")
    print("Reading Census SAIPE poverty data...")
    df = pd.read_excel(path)
    df.columns = [clean_col(c) for c in df.columns]

    print(f"  {len(df):,} rows, {len(df.columns)} columns")
    df.to_sql("census_saipe_poverty", engine, if_exists="replace", index=False,
              method="multi", chunksize=500)
    print("  Loaded census_saipe_poverty ✓")

    with engine.connect() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_saipe_state_dist ON census_saipe_poverty (state, distid)"))
        conn.commit()


if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    load_finances(engine)
    load_saipe(engine)
