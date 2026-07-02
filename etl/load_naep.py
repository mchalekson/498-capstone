"""
Load NAEP assessment data into PostgreSQL.

All four NAEP files (grade 8/12 × math/reading) are stacked into one table.

Table created:
  naep_assessments — state-level NAEP scores (year, state, grade, subject, score)
"""

import os
import pandas as pd
from sqlalchemy import create_engine
from config import DATABASE_URL, DATA_DIR

NAEP_FILES = [
    ("naep_grade8_math_2024_bystate.xls",    8,  "math"),
    ("naep_grade8_reading_2024_bystate.xls", 8,  "reading"),
    ("naep_grade12_math_2024_national.xls",  12, "math"),
    ("naep_grade12_reading_2024_national.xls", 12, "reading"),
]


def parse_naep_file(path: str, grade: int, subject: str) -> pd.DataFrame:
    df = pd.read_excel(path, header=None)

    # Find the header row (contains "Year" and "Jurisdiction")
    header_row = None
    for i, row in df.iterrows():
        vals = [str(v).strip() for v in row.values]
        if "Year" in vals and "Jurisdiction" in vals:
            header_row = i
            break

    if header_row is None:
        raise ValueError(f"Could not find header row in {path}")

    data = pd.read_excel(path, header=header_row)
    data.columns = [str(c).strip().lower().replace(" ", "_") for c in data.columns]
    data = data.dropna(subset=["jurisdiction"])

    # Keep only real state/national rows (skip race/ethnicity sub-rows)
    score_col = next((c for c in data.columns if "score" in c or "scale" in c), data.columns[-1])
    data = data[["year", "jurisdiction", score_col]].copy()
    data.columns = ["year", "state", "avg_scale_score"]
    data["grade"] = grade
    data["subject"] = subject
    data = data.dropna(subset=["avg_scale_score"])

    return data


def load_naep(engine):
    print("Reading NAEP assessment files...")
    frames = []
    for filename, grade, subject in NAEP_FILES:
        path = os.path.join(DATA_DIR, "NAEP", filename)
        df = parse_naep_file(path, grade, subject)
        print(f"  {filename}: {len(df)} rows")
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)
    print(f"  Total: {len(combined):,} rows")
    combined.to_sql("naep_assessments", engine, if_exists="replace", index=False,
                    method="multi", chunksize=500)
    print("  Loaded naep_assessments ✓")


if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    load_naep(engine)
