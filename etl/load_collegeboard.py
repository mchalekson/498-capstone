"""
Load College Board AP data into PostgreSQL.

The CB files are state-level aggregates (not school-level), broken down
by race/ethnicity. Each file has its own layout and gets its own parser.
Each is reshaped into a tidy (long) format: state, subgroup, metric, year, value.

Tables created:
  ap_availability   — % of public HS offering AP courses (>= 5 courses), by state/subgroup
  ap_participation  — % of HS students taking AP exams + total examinees, by state/subgroup
  ap_performance    — distribution of AP exam scores (1-5) by state/subgroup
"""

import os
import pandas as pd
from sqlalchemy import create_engine
from config import DATABASE_URL, DATA_DIR

RACE_SUBGROUPS = {
    "asian", "hispanic/latino", "white", "black/african american",
    "american indian/alaska native", "native hawaiian or other pacific islander",
    "two or more races", "no response",
}


def _is_blank(v) -> bool:
    return v is None or (isinstance(v, float) and pd.isna(v)) or (isinstance(v, str) and not v.strip())


def _to_native(v):
    """Unwrap numpy scalars (e.g. np.float64) to plain Python types so
    psycopg2 can adapt them instead of embedding their repr() as literal SQL."""
    return v.item() if hasattr(v, "item") else v


def parse_availability(path: str) -> pd.DataFrame:
    """
    Layout: three metric blocks sit side by side across the columns
    ("At least five AP courses", "At least ten AP courses",
    "At least one AP STEM course"), each with its own 6 year-range columns.
    Row 2 holds the (forward-filled) threshold label per block, row 3 the
    year-range labels (e.g. "2024-2025"). A row whose data columns are all
    blank is a geography name (National, state...). Otherwise it's a metric
    row (population-wide or a race/ethnicity subgroup) for the current
    geography, repeated across all three blocks.
    """
    raw = pd.read_excel(path, sheet_name="AVAILABILITY", header=None)

    year_row_idx = next(
        i for i, v in raw[2].items() if isinstance(v, str) and "-" in v and v[:4].isdigit()
    )
    threshold_row = raw.iloc[year_row_idx - 1]
    years = raw.iloc[year_row_idx].tolist()

    thresholds = []
    current_threshold = None
    for v in threshold_row:
        if not _is_blank(v):
            current_threshold = str(v).strip()
        thresholds.append(current_threshold)

    records = []
    current_state = None
    for i in range(year_row_idx + 1, len(raw)):
        row = raw.iloc[i]
        label = row[1]
        if _is_blank(label):
            continue
        label = str(label).strip()
        if label == "DATA NOTES:":
            break
        if label.lower() == "by student race/ethnicity":
            continue

        data_cols = row[2:]
        has_data = any(not _is_blank(v) for v in data_cols)
        if not has_data:
            current_state = label
            continue

        if label.lower().startswith("percentage of") and "students whose high school offers" in label.lower():
            subgroup = label[len("Percentage of "):].split(" students whose")[0].strip()
            metric = "pct_students_school_offers"
        else:
            subgroup = "All"
            metric = label.rstrip(":").strip()

        for col_idx, year in enumerate(years):
            if col_idx < 2 or _is_blank(year):
                continue
            val = row[col_idx]
            if _is_blank(val):
                continue
            records.append({
                "state": current_state,
                "subgroup": subgroup,
                "threshold": thresholds[col_idx],
                "metric": metric,
                "year": int(str(year)[:4]),
                "value": _to_native(val),
            })

    return pd.DataFrame(records)


def parse_participation(path: str) -> pd.DataFrame:
    """
    Layout: geography rows carry their own data (subgroup="All"), followed
    directly by fixed-vocabulary race/ethnicity subgroup rows. Three metric
    groups sit side by side: % participation, total examinees, growth rates.
    """
    raw = pd.read_excel(path, sheet_name="PARTICIPATION", header=None)

    metric_groups = [
        ("pct_participation", range(2, 6)),
        ("total_examinees", range(6, 10)),
        ("growth_rate", range(10, 13)),
    ]
    years_row = raw.iloc[4]

    records = []
    current_state = None
    for i in range(5, len(raw)):
        row = raw.iloc[i]
        label = row[1]
        if _is_blank(label):
            continue
        label = str(label).strip()
        if label.lower() == "by examinee race/ethnicity":
            continue

        if label.lower() in RACE_SUBGROUPS:
            subgroup = label
        else:
            subgroup = "All"
            current_state = label

        for metric, cols in metric_groups:
            for col_idx in cols:
                year = years_row[col_idx]
                val = row[col_idx]
                if _is_blank(year) or _is_blank(val):
                    continue
                records.append({
                    "state": current_state,
                    "subgroup": subgroup,
                    "metric": metric,
                    "year": str(year),
                    "value": _to_native(val),
                })

    return pd.DataFrame(records)


def parse_performance(path: str) -> pd.DataFrame:
    """
    Layout: a geography row (all data columns blank) resets current_state.
    A row with a label in col 1 starts a new subgroup; subsequent blank-label
    rows continue that subgroup's score breakdown (5, 4, 3, 2, 1, Total, Mean Score).
    """
    raw = pd.read_excel(path, sheet_name="PERFORMANCE", header=None)

    year_row_idx = next(
        i for i, v in raw[3].items() if isinstance(v, str) and v.strip().isdigit()
    )
    years = raw.iloc[year_row_idx].tolist()

    records = []
    current_state = None
    current_subgroup = None
    for i in range(year_row_idx + 1, len(raw)):
        row = raw.iloc[i]
        label = row[1]

        data_cols = row[2:]
        has_data = any(not _is_blank(v) for v in data_cols)

        if not _is_blank(label):
            label = str(label).strip()
            if label.lower() == "by examinee race/ethnicity":
                continue
            if not has_data:
                current_state = label
                current_subgroup = None
                continue
            current_subgroup = label

        if current_subgroup is None or _is_blank(row[2]):
            continue

        score_category = str(row[2]).strip()
        metric = {"Total": "total_exams", "Mean Score": "mean_score"}.get(
            score_category, f"score_{score_category}"
        )

        for col_idx in range(3, len(row)):
            year = years[col_idx]
            val = row[col_idx]
            if _is_blank(year) or _is_blank(val):
                continue
            records.append({
                "state": current_state,
                "subgroup": current_subgroup,
                "metric": metric,
                "year": str(year),
                "value": _to_native(val),
            })

    return pd.DataFrame(records)


def load_collegeboard(engine):
    files = {
        "ap_availability":  ("CollegeBoard/collegeboard_ap_availability_2024-25.xlsx",  parse_availability),
        "ap_participation": ("CollegeBoard/collegeboard_ap_participation_2024-25.xlsx", parse_participation),
        "ap_performance":   ("CollegeBoard/collegeboard_ap_performance_2024-25.xlsx",   parse_performance),
    }

    for table, (fname, parser) in files.items():
        path = os.path.join(DATA_DIR, fname)
        print(f"Reading {fname}...")
        df = parser(path)
        print(f"  {len(df):,} rows")
        df.to_sql(table, engine, if_exists="replace", index=False,
                  method="multi", chunksize=500)
        print(f"  Loaded {table} ✓")


if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    load_collegeboard(engine)
