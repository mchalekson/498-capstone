"""
Clean Census school finance and SAIPE poverty data after raw load.

Issues addressed:
  Finance:
    - Rename cryptic Census variable codes to human-readable names
    - NCESID renamed to leaid (zero-padded 7-digit string)
    - Revenue/expenditure values are in $1,000s — documented in column comments

  SAIPE:
    - Construct standard 7-digit LEAID: FIPS state (2-digit) + district ID (5-digit)
    - Rename columns to readable names

Produces tables: census_school_finances_clean, census_saipe_poverty_clean
"""

import pandas as pd
from sqlalchemy import create_engine, text
from config import DATABASE_URL

# Subset of Census finance columns we care about (full codebook has 150+)
# Values are in $1,000s per Census documentation
FINANCE_RENAME = {
    "leaid":     "leaid",
    "name":      "district_name",
    "fipst":     "fips_state",
    "state":     "state_code",
    "yrdata":    "fiscal_year",
    "totalrev":  "total_revenue_000s",
    "tfedrev":   "federal_revenue_000s",
    "tstrev":    "state_revenue_000s",
    "tlocrev":   "local_revenue_000s",
    "totalexp":  "total_expenditure_000s",
    "tcurelsc":  "current_exp_elem_secondary_000s",
    "tcurinst":  "instruction_expenditure_000s",
    "tcurssvc":  "support_services_expenditure_000s",
    "tcapout":   "capital_outlay_000s",
    "v33":       "total_salaries_000s",
    "e13":       "instruction_salaries_000s",
    "v91":       "total_benefits_000s",
}

FINANCE_KEEP = list(FINANCE_RENAME.keys())


def clean_finances(engine):
    print("Cleaning Census school finances...")
    df = pd.read_sql("SELECT * FROM census_school_finances", engine)
    df.columns = df.columns.str.lower()

    # NCESID → leaid
    if "ncesid" in df.columns:
        df = df.rename(columns={"ncesid": "leaid"})

    # Zero-pad leaid to 7 digits
    df["leaid"] = df["leaid"].astype(str).str.strip().str.zfill(7)

    # Keep and rename meaningful columns only
    available = [c for c in FINANCE_KEEP if c in df.columns]
    df = df[available].rename(columns=FINANCE_RENAME)

    # Drop rows with no revenue data (aggregates / non-district rows)
    df = df.dropna(subset=["total_revenue_000s"])
    df = df[df["total_revenue_000s"] > 0]

    df.to_sql("census_school_finances_clean", engine, if_exists="replace",
              index=False, method="multi", chunksize=500)
    print(f"  {len(df):,} rows → census_school_finances_clean ✓")

    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE census_school_finances_clean ADD PRIMARY KEY (leaid)"))
        conn.commit()


def clean_saipe(engine):
    print("Cleaning Census SAIPE poverty...")
    df = pd.read_sql("SELECT * FROM census_saipe_poverty", engine)
    df.columns = df.columns.str.lower()

    # Construct standard 7-digit LEAID: 2-digit FIPS state + 5-digit district ID
    df["leaid"] = (
        df["state"].astype(str).str.zfill(2) +
        df["distid"].astype(str).str.zfill(5)
    )

    df = df.rename(columns={
        "name":            "district_name",
        "stabrev":         "state_abbr",
        "rpopall_24":      "total_population",
        "saepov5_17rv_24": "child_poverty_estimate",
        "rpop5_17v_24":    "child_population_5_17",
        "state":           "fips_state",
        "distid":          "fips_distid",
    })

    # Compute poverty rate
    df["pct_child_poverty"] = (
        df["child_poverty_estimate"] / df["child_population_5_17"].replace(0, pd.NA) * 100
    ).round(2)

    df.to_sql("census_saipe_poverty_clean", engine, if_exists="replace",
              index=False, method="multi", chunksize=500)
    print(f"  {len(df):,} rows → census_saipe_poverty_clean ✓")

    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE census_saipe_poverty_clean ADD PRIMARY KEY (leaid)"))
        conn.commit()


if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    clean_finances(engine)
    clean_saipe(engine)
