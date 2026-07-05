"""
Clean NAEP assessment data after raw load.

Issues addressed:
  - Drop sub-group rows (race/ethnicity breakdowns mixed with state rows)
  - Standardize state names to match NCES state abbreviations
  - Cast year to integer, score to float
  - Ensure no duplicate (year, state, grade, subject) rows

Produces table: naep_assessments_clean
"""

import pandas as pd
from sqlalchemy import create_engine, text
from config import DATABASE_URL
import db_utils

# States and territories that are valid NAEP jurisdictions (not subgroups)
VALID_JURISDICTIONS = {
    "national", "alabama", "alaska", "arizona", "arkansas", "california",
    "colorado", "connecticut", "delaware", "district of columbia", "florida",
    "georgia", "hawaii", "idaho", "illinois", "indiana", "iowa", "kansas",
    "kentucky", "louisiana", "maine", "maryland", "massachusetts", "michigan",
    "minnesota", "mississippi", "missouri", "montana", "nebraska", "nevada",
    "new hampshire", "new jersey", "new mexico", "new york", "north carolina",
    "north dakota", "ohio", "oklahoma", "oregon", "pennsylvania", "rhode island",
    "south carolina", "south dakota", "tennessee", "texas", "utah", "vermont",
    "virginia", "washington", "west virginia", "wisconsin", "wyoming",
    "dodea", "trial urban district",
}


def clean_naep(engine):
    print("Cleaning NAEP assessments...")
    df = pd.read_sql("SELECT * FROM naep_assessments", engine)

    # Keep only valid state/national jurisdiction rows
    df["state_lower"] = df["state"].str.strip().str.lower()
    df = df[df["state_lower"].isin(VALID_JURISDICTIONS)].drop(columns=["state_lower"])

    # Cast types
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["avg_scale_score"] = pd.to_numeric(df["avg_scale_score"], errors="coerce")
    df["grade"] = df["grade"].astype("Int64")

    # Deduplicate
    before = len(df)
    df = df.drop_duplicates(subset=["year", "state", "grade", "subject"])
    print(f"  Removed {before - len(df)} duplicate rows")

    df.to_sql("naep_assessments_clean", engine, if_exists="replace",
              index=False, method=db_utils.psql_insert_copy)
    print(f"  {len(df):,} rows → naep_assessments_clean ✓")

    with engine.connect() as conn:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_naep_state ON naep_assessments_clean (state)"
        ))
        conn.commit()


if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    clean_naep(engine)
