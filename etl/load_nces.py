"""
Load NCES public and private school data into PostgreSQL.

Tables created:
  nces_public_schools       — one row per public school (PK: ncessch)
  nces_private_schools      — one row per private school (PK: ncessch)
  nces_public_hs_grades_9_12 — one row per public high school, grades 9-12 only (PK: ncessch)
  nces_private_merged       — one row per private high school, PSS Universe Survey,
                              49-state merge (PK: pss_school_id)
"""

import os
import re
import pandas as pd
from sqlalchemy import create_engine, text
from config import DATABASE_URL, DATA_DIR
import db_utils


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

    # Trailing footer/legend lines in the CSV have no ID — drop them
    df = df.dropna(subset=["ncessch"])

    print(f"  {len(df):,} rows, {len(df.columns)} columns")
    df.to_sql("nces_public_schools", engine, if_exists="replace", index=False,
              method=db_utils.psql_insert_copy)
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

    # Trailing footer/legend lines in the CSV have no ID — drop them
    df = df.dropna(subset=["ncessch"])

    print(f"  {len(df):,} rows, {len(df.columns)} columns")
    df.to_sql("nces_private_schools", engine, if_exists="replace", index=False,
              method=db_utils.psql_insert_copy)
    print("  Loaded nces_private_schools ✓")

    with engine.connect() as conn:
        conn.execute(text(
            "ALTER TABLE nces_private_schools ADD PRIMARY KEY (ncessch)"
        ))
        conn.commit()


def load_public_hs912(engine):
    path = os.path.join(DATA_DIR, "NCES", "ELSI_csv_new_updated.csv")
    print("Reading NCES public high schools (grades 9-12)...")
    df = pd.read_csv(path, skiprows=6, low_memory=False)
    df.columns = [clean_col(c) for c in df.columns]

    id_col = next(c for c in df.columns if "school_id" in c or "nces" in c)
    df = df.rename(columns={id_col: "ncessch"})

    df = df.drop(columns=["school_name"], errors="ignore")  # duplicate of later col

    df = df.dropna(subset=["ncessch"])

    print(f"  {len(df):,} rows, {len(df.columns)} columns")
    df.to_sql("nces_public_hs_grades_9_12", engine, if_exists="replace", index=False,
              method=db_utils.psql_insert_copy)
    print("  Loaded nces_public_hs_grades_9_12 ✓")

    with engine.connect() as conn:
        conn.execute(text(
            "ALTER TABLE nces_public_hs_grades_9_12 ADD PRIMARY KEY (ncessch)"
        ))
        conn.commit()


def load_public_id12(engine):
    """Build the 7<->12-digit NCES ID bridge (nces_public_id12_bridge).

    build_ceeb_crosswalk.py joins our 7-digit ncessch to the NU master's
    12-digit NCES IDs, so it needs a lookup between the two. Both IDs live in
    the same ELSI re-pull that feeds nces_public_hs_grades_9_12; here we pull
    just the two ID columns (as text — 12-digit IDs are fixed-width and can
    carry leading zeros) into a dedicated bridge table.
    """
    path = os.path.join(DATA_DIR, "NCES", "ELSI_csv_new_updated.csv")
    print("Building NCES 7<->12-digit ID bridge...")
    hdr = pd.read_csv(path, skiprows=6, nrows=0)
    c7 = next(c for c in hdr.columns if "(7-digit)" in c)
    c12 = next(c for c in hdr.columns if "(12-digit)" in c)
    df = pd.read_csv(path, skiprows=6, usecols=[c7, c12], dtype=str)
    df = df.rename(columns={c7: "ncessch", c12: "ncessch12"})
    df = df.dropna(subset=["ncessch"]).drop_duplicates(subset=["ncessch"])

    print(f"  {len(df):,} rows ({df['ncessch12'].notna().sum():,} with a 12-digit ID)")
    df.to_sql("nces_public_id12_bridge", engine, if_exists="replace", index=False,
              method=db_utils.psql_insert_copy)
    print("  Loaded nces_public_id12_bridge ✓")

    with engine.connect() as conn:
        conn.execute(text(
            "ALTER TABLE nces_public_id12_bridge ADD PRIMARY KEY (ncessch)"
        ))
        conn.commit()


def load_private_merged(engine):
    path = os.path.join(DATA_DIR, "NCES", "NCES_private_merged.csv")
    print("Reading NCES private schools (49-state PSS merge)...")
    df = pd.read_csv(path, low_memory=False)
    df.columns = [clean_col(c) for c in df.columns]

    print(f"  {len(df):,} rows, {len(df.columns)} columns")
    df.to_sql("nces_private_merged", engine, if_exists="replace", index=False,
              method=db_utils.psql_insert_copy)
    print("  Loaded nces_private_merged ✓")

    with engine.connect() as conn:
        conn.execute(text(
            "ALTER TABLE nces_private_merged ADD PRIMARY KEY (pss_school_id)"
        ))
        conn.commit()


if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    load_public(engine)
    load_private(engine)
    load_public_hs912(engine)
    load_public_id12(engine)
    load_private_merged(engine)
