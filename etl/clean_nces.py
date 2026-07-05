"""
Clean NCES public and private school data after raw load.

Issues addressed:
  - NCESSCH stored as float → zero-padded 7-digit string
  - LEAID not in file → derived from first 5 digits of NCESSCH
  - Suppression symbols (†, –, ‡) in numeric columns → NULL
  - Duplicate NCESSCH rows → keep first occurrence
  - Column names normalized to snake_case (already done in load step)

Produces tables: nces_public_schools_clean, nces_private_schools_clean
"""

import re
import pandas as pd
from sqlalchemy import create_engine, text
from config import DATABASE_URL

# NCES standard suppression codes
SUPPRESSED = {"†", "‡", "–", "-", "n/a", "na", "not applicable", "not available"}


def clean_col(name: str) -> str:
    name = re.sub(r"\[.*?\]", "", name)
    name = re.sub(r"\(.*?\)", "", name)
    name = name.strip().lower()
    name = re.sub(r"[^\w]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name


def coerce_numeric(series: pd.Series) -> pd.Series:
    """Replace NCES suppression symbols with NaN, then cast to numeric."""
    cleaned = series.astype(str).str.strip()
    cleaned = cleaned.replace(SUPPRESSED, pd.NA)
    return pd.to_numeric(cleaned, errors="coerce")


def pad_ncessch(series: pd.Series) -> pd.Series:
    """Convert float NCESSCH (e.g. 601195.0) to zero-padded 7-digit string."""
    return (
        series.astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
        .str.zfill(7)
    )


def clean_public(engine):
    print("Cleaning NCES public schools...")
    df = pd.read_sql("SELECT * FROM nces_public_schools", engine)

    # Fix NCESSCH
    df["ncessch"] = pad_ncessch(df["ncessch"])

    # Derive LEAID from first 5 digits of NCESSCH
    df["leaid"] = df["ncessch"].str[:5]

    # Deduplicate
    before = len(df)
    df = df.drop_duplicates(subset=["ncessch"], keep="first")
    print(f"  Removed {before - len(df)} duplicate NCESSCH rows")

    # Coerce all numeric columns (suppress symbols → NULL)
    numeric_keywords = [
        "students", "eligible", "ratio", "teachers", "grade_9", "grade_10",
        "grade_11", "grade_12", "male", "female", "american_indian",
        "asian", "hispanic", "black", "white", "pacific", "two_or_more",
        "ansi", "fips"
    ]
    for col in df.columns:
        if any(kw in col for kw in numeric_keywords):
            df[col] = coerce_numeric(df[col])

    df.to_sql("nces_public_schools_clean", engine, if_exists="replace",
              index=False, method="multi", chunksize=500)
    print(f"  {len(df):,} rows → nces_public_schools_clean ✓")

    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE nces_public_schools_clean ADD PRIMARY KEY (ncessch)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_pub_leaid ON nces_public_schools_clean (leaid)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_pub_state ON nces_public_schools_clean (location_state_abbr_2024_25)"))
        conn.commit()


def clean_private(engine):
    print("Cleaning NCES private schools...")
    df = pd.read_sql("SELECT * FROM nces_private_schools", engine)

    df["ncessch"] = pad_ncessch(df["ncessch"])
    df = df.drop_duplicates(subset=["ncessch"], keep="first")

    df.to_sql("nces_private_schools_clean", engine, if_exists="replace",
              index=False, method="multi", chunksize=500)
    print(f"  {len(df):,} rows → nces_private_schools_clean ✓")

    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE nces_private_schools_clean ADD PRIMARY KEY (ncessch)"))
        conn.commit()


if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    clean_public(engine)
    clean_private(engine)
