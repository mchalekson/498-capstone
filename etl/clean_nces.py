"""
Clean NCES public and private school data after raw load.

Issues addressed:
  - NCESSCH stored as float → zero-padded 7-digit string
  - LEAID not in file → derived from first 5 digits of NCESSCH
  - Suppression symbols (†, –, ‡) in numeric columns → NULL
  - Duplicate NCESSCH rows → keep first occurrence
  - Column names normalized to snake_case (already done in load step)

Produces tables: nces_public_schools_clean, nces_private_schools_clean,
                 nces_private_merged_clean
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


def clean_private_merged(engine):
    """
    Cleaning to-dos from the EDA (EDA_NCES_private_EN.md):
      - drop fully-empty columns (10 PSS_ENROLL_* grade columns that don't
        apply to high schools, plus 3 unused PSS_ASSOC_* slots)
      - -1 is PSS's missing-data sentinel on pss_coed, pss_type, pss_orient -> NULL
      - numeric columns are already typed correctly by pandas/Postgres, no cast needed
      - student/teacher ratio outliers (up to 409.9): checked against
        enrollment/FTE directly (e.g. 6353 students / 15.5 FTE teachers ~= 409.87)
        and are consistent, not data errors -> kept as-is
      - race-percentage backfill from ELSI (nces_private_schools_clean): skipped.
        ELSI reports one combined "asian_or_asian_pacific_islander" figure while
        PSS keeps Asian and Pacific Islander as separate categories, so backfilling
        would conflate two distinct groups rather than fill in a missing one
    """
    print("Cleaning NCES private schools (49-state PSS merge)...")
    df = pd.read_sql("SELECT * FROM nces_private_merged", engine)

    empty_cols = df.columns[df.isna().all()].tolist()
    df = df.drop(columns=empty_cols)
    print(f"  Dropped {len(empty_cols)} fully-empty columns: {empty_cols}")

    for col in ("pss_coed", "pss_type", "pss_orient"):
        n = (df[col] == -1).sum()
        df[col] = df[col].replace(-1, pd.NA)
        print(f"  {col}: {n} sentinel -1 values -> NULL")

    df.to_sql("nces_private_merged_clean", engine, if_exists="replace",
              index=False, method="multi", chunksize=500)
    print(f"  {len(df):,} rows → nces_private_merged_clean ✓")

    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE nces_private_merged_clean ADD PRIMARY KEY (pss_school_id)"))
        conn.commit()


if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    clean_public(engine)
    clean_private(engine)
    clean_private_merged(engine)
