"""
Load College Board AP data into PostgreSQL.

The CB files are state-level aggregates (not school-level), broken down
by race/ethnicity. Each file is loaded into its own table.

Tables created:
  ap_availability   — % of public HS offering ≥5, ≥10, ≥1 STEM AP courses
  ap_participation  — % of HS students taking AP exams + total examinees
  ap_performance    — distribution of AP exam scores (1–5) by state
"""

import os
import re
import pandas as pd
from sqlalchemy import create_engine
from config import DATABASE_URL, DATA_DIR


def parse_ap_file(path: str, sheet: str) -> pd.DataFrame:
    """
    Parse a College Board AP file.

    These files use a multi-row header with merged cells. The pattern is:
      - Col 0: blank
      - Col 1: geography (National / State / race subgroup)
      - Col 2+: metric values across years

    We reconstruct a tidy (long) format: state, subgroup, metric, year, value.
    """
    raw = pd.read_excel(path, sheet_name=sheet, header=None)

    # Find the row that has year values (e.g. 2025, 2024, 2020...)
    year_row_idx = None
    for i, row in raw.iterrows():
        vals = [v for v in row.values if isinstance(v, (int, float)) and 2010 <= v <= 2030]
        if len(vals) >= 2:
            year_row_idx = i
            break

    if year_row_idx is None:
        raise ValueError(f"Could not find year row in {path}")

    # Build column labels from metric header rows above year row
    metric_rows = raw.iloc[max(0, year_row_idx - 3): year_row_idx]
    year_row = raw.iloc[year_row_idx]

    # Forward-fill metric names across merged cells
    metric_labels = []
    current = ""
    for cell in metric_rows.iloc[-1]:  # use last metric row
        if pd.notna(cell) and str(cell).strip():
            current = str(cell).strip()
        metric_labels.append(current)

    years = [str(int(v)) if isinstance(v, float) else str(v) for v in year_row]

    # Data starts after year row
    data = raw.iloc[year_row_idx + 1:].copy()
    data.columns = range(len(data.columns))

    records = []
    current_state = None
    current_subgroup = None

    for _, row in data.iterrows():
        label = str(row[1]).strip() if pd.notna(row[1]) else ""
        if not label or label == "nan":
            continue

        # Detect if this is a state/national row or a subgroup row
        is_state = label in (
            ["National"] + [s for s in row[1:2].values if isinstance(s, str) and len(s) > 3]
        )
        # Heuristic: subgroups contain "/" or are known race labels
        race_keywords = {"asian", "hispanic", "white", "black", "native", "two or more", "no response"}
        is_subgroup = any(kw in label.lower() for kw in race_keywords)

        if not is_subgroup:
            current_state = label
            current_subgroup = "All"
        else:
            current_subgroup = label

        for col_idx in range(2, len(row)):
            val = row[col_idx]
            if pd.isna(val):
                continue
            metric = metric_labels[col_idx] if col_idx < len(metric_labels) else ""
            year = years[col_idx] if col_idx < len(years) else ""
            records.append({
                "state": current_state,
                "subgroup": current_subgroup,
                "metric": metric,
                "year": year,
                "value": val,
            })

    return pd.DataFrame(records)


def load_collegeboard(engine):
    files = {
        "ap_availability":  ("CollegeBoard/collegeboard_ap_availability_2024-25.xlsx",  "AVAILABILITY"),
        "ap_participation": ("CollegeBoard/collegeboard_ap_participation_2024-25.xlsx", "PARTICIPATION"),
        "ap_performance":   ("CollegeBoard/collegeboard_ap_performance_2024-25.xlsx",   "PERFORMANCE"),
    }

    for table, (fname, sheet) in files.items():
        path = os.path.join(DATA_DIR, fname)
        print(f"Reading {fname}...")
        df = parse_ap_file(path, sheet)
        print(f"  {len(df):,} rows")
        df.to_sql(table, engine, if_exists="replace", index=False,
                  method="multi", chunksize=500)
        print(f"  Loaded {table} ✓")


if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    load_collegeboard(engine)
