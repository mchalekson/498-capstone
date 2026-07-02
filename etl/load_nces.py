"""
Load NCES public and private school data into PostgreSQL.

Tables created:
  nces_public_schools  — one row per public school (PK: ncessch)
  nces_private_schools — one row per private school (PK: ncessch)
"""

import os
import re
import pandas as pd
from sqlalchemy import create_engine, text
from config import DATABASE_URL, DATA_DIR


def clean_col(name: str) -> str:
    """Normalize column names to snake_case."""
    name = re.sub(r"\[.*?\]", "", name)        # strip [Public School] suffixes
    name = re.sub(r"\(.*?\)", "", name)        # strip (SY 2017...) notes
    name = name.strip().lower()
    name = re.sub(r"[^\w]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name


def load_public(engine):
    path = os.path.join(DATA_DIR, "NCES", "nces-public-schools.csv")
    print("Reading NCES public schools...")
    df = pd.read_csv(path, skiprows=6, low_memory=False)
    df.columns = [clean_col(c) for c in df.columns]

    # Rename the NCES school ID to a consistent key
    id_col = next(c for c in df.columns if "school_id" in c or "nces" in c)
    df = df.rename(columns={id_col: "ncessch"})

    df = df.drop(columns=["school_name"], errors="ignore")  # duplicate of later col

    print(f"  {len(df):,} rows, {len(df.columns)} columns")
    df.to_sql("nces_public_schools", engine, if_exists="replace", index=False,
              method="multi", chunksize=500)
    print("  Loaded nces_public_schools ✓")

    with engine.connect() as conn:
        conn.execute(text(
            "ALTER TABLE nces_public_schools ADD PRIMARY KEY (ncessch)"
        ))
        conn.commit()


def load_private(engine):
    path = os.path.join(DATA_DIR, "NCES", "nces-private-schools.csv")
    print("Reading NCES private schools...")
    df = pd.read_csv(path, skiprows=6, low_memory=False)
    df.columns = [clean_col(c) for c in df.columns]

    id_col = next(c for c in df.columns if "school_id" in c or "nces" in c)
    df = df.rename(columns={id_col: "ncessch"})

    print(f"  {len(df):,} rows, {len(df.columns)} columns")
    df.to_sql("nces_private_schools", engine, if_exists="replace", index=False,
              method="multi", chunksize=500)
    print("  Loaded nces_private_schools ✓")

    with engine.connect() as conn:
        conn.execute(text(
            "ALTER TABLE nces_private_schools ADD PRIMARY KEY (ncessch)"
        ))
        conn.commit()


if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    load_public(engine)
    load_private(engine)
