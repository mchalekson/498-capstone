"""Data dictionary for the 29 v5 rigor fields appended to the client delivery workbook.

The v5 index ships inside `Capstone_Org_Data_extended_v5_2026-07-31.xlsx`, whose
`README_v5` sheet documents the fields a reader needs first but not the full set.
This script emits the complete per-field dictionary in the same schema the modeling
dataset uses (`data_dictionary_modeling_dataset_v4.csv`), so both tracks read alike.

Run from anywhere:

    python etl/build_rigor_v5_dictionary.py

Writes `csv_exports/data_dictionary_rigor_v5.csv`. Spec: `docs/RIGOR_FORMULA_V5.md`.
"""

import os
import sys

import pandas as pd

# Resolved against the repo root, not the working directory, so the script writes
# the same file wherever it is run from.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKBOOK = os.path.join(ROOT, "Capstone_Org_Data_extended_v5_2026-07-31.xlsx")
OUT = os.path.join(ROOT, "csv_exports", "data_dictionary_rigor_v5.csv")
SHEET = "Export"

SPEC = "docs/RIGOR_FORMULA_V5.md (31 July 2026); code etl/build_rigor_v5.py"
VINTAGE = "Index built 2026-07-31 from Capstone_Org_Data_extended_v4_full_2026-07-31.xlsx"

# Component weights, from the specification table in RIGOR_FORMULA_V5.md.
COMPONENTS = {
    "C_ap_opportunity": (0.15, "AP tests taken; tests offered; classes offered (band); take rate; Capstone flag"),
    "C_ap_performance": (0.20, "AP qualifying density QD = tests-per-student x P(score >= 3)"),
    "C_advanced_access": (0.10, "AP participation (CRDC); dual-enrollment rate"),
    "C_ib": (0.05, "IB intensity IBint"),
    "C_stem_depth": (0.10, "STEM breadth 0-4 (calculus, advanced math, chemistry, physics)"),
    "C_test_performance": (0.20, "mean SAT; ACT composite (IL)"),
    "C_test_participation": (0.05, "test-taker rate; SAT participation"),
    "C_college_placement": (0.10, "% to college; % to four-year (band midpoints)"),
    "C_faculty_investment": (0.05, "% teachers certified; instructional spend per pupil"),
}

# description, then the caveat a reader needs at the point of use.
FIELDS = {
    "v5_in_universe": (
        "TRUE = high school inside the v5 scoring universe (45,250 of 49,268 rows)",
        "FALSE = college or test record, removed by CEEB length = 4 OR Category = College"),
    "rigor_score_v5": (
        "Continuous weighted composite over the nine components, z-score based",
        "Null where index weight coverage < 0.25. SHIPPED SCORE"),
    "rigor_score_v5_raw": (
        "Composite before proportional reallocation across observed components",
        "Diagnostic only -- not comparable across schools with different coverage"),
    "rigor_tier_num_v5": (
        "Five-tier ordinal 1-5, Jenks natural breaks on rigor_score_v5",
        "Numeric twin of rigor_tier_label_v5"),
    "rigor_tier_label_v5": (
        "Five-tier label, Jenks natural breaks: Below Average .. Most Demanding",
        "PRIMARY FIELD for admissions use. 22,869 scored; 1,441 Most Demanding"),
    "rigor_tier_num_v5_quantile": (
        "Equal-frequency tier number, cut-point sensitivity check",
        "Do not ship -- alternate tiering, not the delivered assignment"),
    "rigor_tier_label_v5_quantile": (
        "Equal-frequency tier label, cut-point sensitivity check",
        "Do not ship -- alternate tiering, not the delivered assignment"),
    "rigor_score_v5_sector": (
        "Composite standardized within public / private separately",
        "Alternative to the pooled score -- client decision pending"),
    "rigor_tier_num_v5_sector": (
        "Within-sector tier number",
        "Alternative to pooled -- client decision pending"),
    "rigor_tier_label_v5_sector": (
        "Within-sector tier label",
        "Alternative to pooled -- client decision pending"),
    "rigor_expected_ses": (
        "Score predicted from socioeconomic context (district child poverty, FRL rate)",
        "Fitted value only; the residual below is the usable measure"),
    "rigor_residual_v5": (
        "rigor_score_v5 minus rigor_expected_ses -- rigor above/below SES expectation",
        "Use for gap detection, NOT as a rigor measure. Correlation with poverty ~= 0"),
    "overperformer_v5": (
        "TRUE = residual above its 90th percentile -- 'does a lot with little'",
        "343 of these are high-need schools, a 5x increase over the raw top tier"),
    "below_coverage_floor": (
        "TRUE = observed index weight below the 0.25 floor, so left unscored",
        "6,167 schools. Logged unscored, never defaulted to a middle tier"),
    "n_components": (
        "Count of the nine components the school actually reports (0-9)",
        "Private schools cap at 6: three components are CRDC-only by statute"),
    "rigor_n_components_v5": (
        "Count of the nine components present, as delivered in the workbook",
        "Same construct as n_components"),
    "weight_covered": (
        "Share of total index weight present for this school, 0-1",
        "Floor is 0.25; below that rigor_score_v5 is null"),
    "rigor_weight_covered_v5": (
        "Share of index weight present, as delivered in the workbook",
        "Same construct as weight_covered"),
    "components_available": (
        "Which of the nine components were present, pipe-delimited",
        "Read with weight_covered to judge how much of the index a score rests on"),
    "rigor_components_available_v5": (
        "Components present, as delivered in the workbook",
        "Same construct as components_available"),
    "rigor_weighting_scheme_v5": (
        "Identifier of the weight vector used",
        "Constant across rows; provenance stamp"),
    "rigor_tier_method_v5": (
        "Tiering method used for the shipped tier (Jenks natural breaks)",
        "Constant across rows; provenance stamp"),
    "qd": (
        "AP qualifying density, derived input to C_ap_performance",
        "Winsorized 1st/99th pct. 1.2 within-school score SD is a documented approximation"),
    "ib_int": (
        "IB intensity, derived input to C_ib",
        "CRDC IB enrolment / grade 9-12 enrolment, else the verified IB flag"),
    "stem_breadth": (
        "Count of four CRDC STEM offering flags, 0-4, derived input to C_stem_depth",
        "73% of public schools sit at 3 or 4 -- low discriminating power by design"),
    "pct_college": (
        "College-going percentage from org export band midpoints, input to C_college_placement",
        "Band midpoints; open-ended bands take 0.5x / 1.05x the bound"),
}

# v4 columns that ride along in the same workbook -- the documented trap.
V4_LEFTOVERS = {
    "rigor_score": "v4 index score. SUPERSEDED -- present for comparison only, use rigor_score_v5",
    "rigor_tier_num": "v4 tier number. SUPERSEDED -- use rigor_tier_num_v5",
    "rigor_tier_label": "v4 tier label. SUPERSEDED -- use rigor_tier_label_v5. WARNING: unsuffixed name, easily mistaken for the shipped tier; it scores 18,412 schools and only 108 Most Demanding against v5's 22,869 and 1,441",
    "rigor_n_components_used": "v4 component count. SUPERSEDED -- use rigor_n_components_v5",
    "rigor_components_available": "v4 components present. SUPERSEDED -- use rigor_components_available_v5",
}


def observed_range(s):
    """Numeric columns get min-max; everything else gets a distinct count."""
    nn = s.dropna()
    if nn.empty:
        return "all null"
    if pd.api.types.is_bool_dtype(s) or set(nn.unique()) <= {True, False}:
        return f"{int(nn.sum())} True / {int((~nn.astype(bool)).sum())} False"
    num = pd.to_numeric(nn, errors="coerce").dropna()
    if len(num) == len(nn):
        return f"{num.min():.4g} to {num.max():.4g}"
    return f"{nn.nunique()} distinct values"


def main():
    if not os.path.exists(WORKBOOK):
        sys.exit(f"{WORKBOOK} not found -- the delivery workbook must be at the repo root")

    df = pd.read_excel(WORKBOOK, sheet_name=SHEET)
    n = len(df)
    rows = []

    def add(var, desc, notes, source):
        if var not in df.columns:
            return
        s = df[var]
        rows.append({
            "variable": var,
            "data_type": str(s.dtype),
            "source_dataset": source,
            "grain": "school",
            "vintage_as_of": VINTAGE,
            "vintage_confidence": "confirmed",
            "range": observed_range(s),
            "pct_non_null": round(100.0 * s.notna().sum() / n, 1),
            "description": f"{desc}. {notes}" if notes else desc,
        })

    for var, (desc, notes) in FIELDS.items():
        add(var, desc, notes, SPEC)

    for var, (w, subs) in COMPONENTS.items():
        add(var, f"Component z-score, weight {w:.2f} of 1.00. Sub-features: {subs}",
            "Null = component not reported by this school", SPEC)

    for var, desc in V4_LEFTOVERS.items():
        add(var, desc, "", "etl/build_rigor_classification.py (v4 chain)")

    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False)
    print(f"wrote {os.path.relpath(OUT, ROOT)}: {len(out)} variables documented, over {n:,} workbook rows")

    documented = set(out.variable)
    appended = [c for c in df.columns
                if c.startswith("C_") or "v5" in c or c in V4_LEFTOVERS
                or c in ("qd", "ib_int", "stem_breadth", "pct_college",
                         "n_components", "weight_covered", "components_available",
                         "below_coverage_floor", "overperformer_v5")]
    missing = [c for c in appended if c not in documented]
    print(f"  appended fields found: {len(appended)}; undocumented: {missing or 'none'}")


if __name__ == "__main__":
    main()
