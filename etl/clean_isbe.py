"""
Clean ISBE Illinois Report Card data after raw load.

Issues addressed:
  - Mixed granularity: Statewide/District/School rows → filter to School only
  - Suppression symbol (*) in numeric columns → NULL
  - RCDTS code retained as-is (it is the Illinois school identifier)
  - Percentage columns stored as strings like "12.5%" → float

Produces tables: isbe_<sheet>_clean for each loaded ISBE sheet.
"""

import re
import pandas as pd
from sqlalchemy import create_engine, text
from config import DATABASE_URL
import db_utils

SUPPRESSED = {"*", "n/a", "na", "†", "‡", "–"}

ISBE_TABLES = [
    "isbe_general",
    "isbe_act",
    "isbe_iar",
    "isbe_isa",
    "isbe_cte",
    "isbe_discipline",
    "isbe_finance",
    "isbe_kids",
    "isbe_sped",
]


def coerce_numeric(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.strip()
        .str.replace("%", "", regex=False)
        .replace(SUPPRESSED, pd.NA)
    )
    return pd.to_numeric(cleaned, errors="coerce")


def clean_isbe_table(engine, table: str):
    try:
        df = pd.read_sql(f"SELECT * FROM {table}", engine)
    except Exception:
        print(f"  {table} not found, skipping")
        return

    # Filter to school-level rows only (where 'level' column exists)
    if "level" in df.columns:
        before = len(df)
        df = df[df["level"].str.strip().str.lower() == "school"].copy()
        print(f"  {table}: filtered {before} → {len(df)} school-level rows")

    # Coerce numeric columns
    for col in df.columns:
        if col in ("rcdts", "level", "school_name", "district", "city",
                   "county", "district_type", "school_type", "grades_served",
                   "summative_designation", "summative_designation_student_group_s",
                   "title_i_status", "state_senate_district", "state_house_district",
                   "destinationtable"):
            continue
        if df[col].dtype == object:
            numeric_candidate = coerce_numeric(df[col])
            # Only replace if at least 30% of non-null values parsed successfully
            non_null = df[col].notna().sum()
            parsed = numeric_candidate.notna().sum()
            if non_null > 0 and parsed / non_null >= 0.3:
                df[col] = numeric_candidate

    clean_table = f"{table}_clean"
    df.to_sql(clean_table, engine, if_exists="replace", index=False,
              method=db_utils.psql_insert_copy)
    print(f"  {len(df):,} rows → {clean_table} ✓")

    if "rcdts" in df.columns:
        with engine.connect() as conn:
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{table}_rcdts ON {clean_table} (rcdts)"))
            conn.commit()


def clean_isbe(engine):
    print("Cleaning ISBE tables...")
    for table in ISBE_TABLES:
        clean_isbe_table(engine, table)


if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    clean_isbe(engine)
