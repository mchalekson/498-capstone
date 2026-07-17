"""
build_modeling_dataset.py  —  cleaning freeze on top of build_features.py's output.

Applies the freeze rules agreed for the first versioned modeling dataset:
  - minimum-size threshold: grades 9-12 enrollment >= 30 (schools smaller than
    that make rates/percentiles too noisy to trust as model inputs)
  - restrict to the actual analysis universe (public HS ∪ private HS) --
    org-only / non-HS rows ("other/oos": colleges, unmatched junk, etc.) are
    out of scope for a school-rigor model and are dropped here, not upstream,
    so build_features.py's output still shows the full join for auditing
  - sentinel/suppression codes -> NaN (defensive pass; CRDC/NCES inputs were
    already clean coming out of build_features.py as of this writing -- see
    the printed counts below, which should read zero unless an upstream input
    changes)
  - ratio columns are winsorized (already done in build_features.py; this
    step only verifies nothing came through unclipped)
  - IB flag is already gated on match tier upstream (ib_flag_candidate)

Does NOT decide the Goal 3 rigor label -- no ground truth exists yet (see
EDA_features_joined.md section 6). This script only freezes the feature set.

Run:  python build_modeling_dataset.py schools_features.csv --version v1
Produces: modeling_dataset_<version>_<date>.csv + data_dictionary_modeling_dataset.csv
"""
import argparse
import datetime as dt
import os
import numpy as np
import pandas as pd

MIN_ENROLLMENT_9_12 = 30

# NCES/Census suppression sentinels seen across these source files. Values are
# checked only within columns whose name suggests a count/rate (see
# SENTINEL_SUSPECT_KEYWORDS) to avoid clobbering legitimate small integers
# elsewhere (e.g. a school literally reporting 0 AP classes).
SENTINEL_VALUES = {-1, -2, -3, -5, -6, -8, -9}
SENTINEL_SUSPECT_KEYWORDS = ("rate", "pct", "percent", "index", "score", "revenue", "funding")

RATIO_COLS = ["ap_participation", "testtaker_rate", "per_resident_child_funding_total",
              "per_resident_child_funding_state_local"]

DESCRIPTIONS = {
    "ceeb": "College Board CEEB code (join key back to schools_org_all)",
    "school_name": "School name, school-side if matched else NU org name",
    "state": "State abbreviation",
    "is_school_match": "True if row matched both a school-side record and an NU org record",
    "is_public_hs": "True if school-side record present and school_level in {High, Secondary}",
    "is_private_hs": "True if NU-flagged private type OR has a school-side pss_id, and not public",
    "sector": "public / private / other-oos -- other-oos rows are excluded from modeling_dataset",
    "has_nu_analytics": "True if nu_avg_num_ap_tests_taken or nu_avg_freshman_sat is present",
    "has_nu_data": "True if row matched any NU org record (nu_guid present) -- broader than has_nu_analytics",
    "socio_need_index": "Mean of 5 NU socio need percentiles (higher = more disadvantage; reverse-coded, see EDA 3a)",
    "ap_offered": "1 if any AP signal present (CRDC offered/enrollment or NU tests taken/offered)",
    "ap_tests_taken": "NU avg AP tests taken per student (Goal 8, direct measure)",
    "ap_participation": "CRDC AP enrollment / enrollment_9_12, winsorized 1/99pct (Goal 8, fallback measure)",
    "ap_intensity_src": "Provenance of the best available AP intensity signal for this row",
    "testtaker_rate": "CRDC SAT/ACT takers / enrollment_9_12, winsorized 1/99pct (Goal 6)",
    "sat_participation_nu": "NU pct of seniors taking SAT (Goal 6)",
    "sat_score_nu": "NU avg freshman SAT score -- NOTE recruiting-selection biased, not a random sample",
    "grad_rate_2021": "EDFacts SY2020-21 four-year adjusted cohort graduation rate",
    "frl_rate": "Free/reduced lunch students / total_enrollment, percent",
    "enrollment_9_12": "Grades 9-12 headcount (denominator for AP/SAT rates and the min-size freeze)",
    "child_poverty_saipe": "County-level SAIPE child poverty percent (r=0.89 with ACS, kept as the single poverty proxy)",
    "per_pupil_state_local": "IL ISBE true per-pupil state+local expenditure (IL only, ~2.8% coverage)",
    "leaid": "District ID, derived as nces_id_12[:7] (NOT the leaid column shipped in schools_org_all -- see build_features.build_funding)",
    "district_total_revenue": "Census F-33 district total revenue, dollars (raw units, from $1,000s source)",
    "per_resident_child_funding_total": "F-33 total revenue / SAIPE school-age (5-17) population, winsorized -- a per-resident-child PROXY, not true per-pupil expenditure (Goal 4, national)",
    "per_resident_child_funding_state_local": "Same as above, state+local revenue only (excludes federal)",
    "funding_source": "Which funding figure is populated for this row: isbe_il_true_per_pupil / census_f33_per_resident_child_proxy / none",
    "percent_going_to_college_mid": "NU bucketed percent going to any college, parsed to bucket midpoint",
    "percent_going_to_4yr_college_mid": "NU bucketed percent going to 4-year college, parsed to bucket midpoint",
    "percent_federal_lunch_aid_mid": "NU bucketed percent on federal lunch aid, parsed to bucket midpoint",
    "percent_first_gen_college_mid": "NU bucketed percent first-gen college, parsed to bucket midpoint",
    "number_of_ap_classes_offered_mid": "NU bucketed count of AP classes offered, parsed to bucket midpoint",
    "size_of_senior_class_mid": "NU bucketed senior class size, parsed to bucket midpoint",
    "ap_capstone": "1 if NU flags this as an AP Capstone school",
    "setting": "Urban/suburban/rural setting, NU value falling back to NCES locale",
    "ib_flag_candidate": "1 if IB fuzzy-matched AND match tier is 'review' (never auto_accept nationwide -- still needs human confirmation, see build_features.py)",
    "meets_min_size": "True if enrollment_9_12 >= 30 or enrollment_9_12 is unknown (freeze gate; see MIN_ENROLLMENT_9_12)",
}


def apply_sentinel_scrub(df):
    suspect_cols = [c for c in df.columns if any(k in c.lower() for k in SENTINEL_SUSPECT_KEYWORDS)
                    and pd.api.types.is_numeric_dtype(df[c])]
    total_hits = 0
    for c in suspect_cols:
        hits = df[c].isin(SENTINEL_VALUES)
        n = int(hits.sum())
        if n:
            print(f"  [sentinel] {c}: {n} sentinel value(s) -> NaN")
            df.loc[hits, c] = np.nan
            total_hits += n
    if not total_hits:
        print(f"  [sentinel] checked {len(suspect_cols)} rate/score/revenue columns, 0 sentinel values found")
    return df


RATE_COL_BOUND = {"ap_participation": 1.0, "testtaker_rate": 1.0}


def check_winsorized(df):
    # Recomputing quantiles on already-clipped data and comparing against itself
    # is circular (tie-heavy interpolation always finds a few "beyond" points) --
    # this just sanity-checks the clipped range against a known sane bound instead.
    for c in RATIO_COLS:
        if c not in df.columns:
            continue
        s = pd.to_numeric(df[c], errors="coerce").dropna()
        if s.empty:
            continue
        bound = RATE_COL_BOUND.get(c)
        flag = ""
        if bound is not None and s.max() > bound:
            flag = f"  !! exceeds sane bound {bound}"
        print(f"  [winsorize check] {c}: range [{s.min():.3g}, {s.max():.3g}]{flag}")


def apply_min_size_freeze(df):
    enr = pd.to_numeric(df["enrollment_9_12"], errors="coerce")
    df["meets_min_size"] = enr.isna() | (enr >= MIN_ENROLLMENT_9_12)
    dropped = int((~df["meets_min_size"]).sum())
    print(f"  [min-size] {dropped} row(s) with enrollment_9_12 < {MIN_ENROLLMENT_9_12} dropped")
    return df[df["meets_min_size"]].copy()


def restrict_to_hs_universe(df):
    before = len(df)
    universe = df[df["is_public_hs"] | df["is_private_hs"]].copy()
    print(f"  [universe] restricted to is_public_hs | is_private_hs: {before:,} -> {len(universe):,} rows "
          f"({before - len(universe):,} other/oos rows dropped -- out of scope for a school-rigor model)")
    return universe


def write_data_dictionary(df, out_path):
    rows = []
    for c in df.columns:
        rows.append({
            "column": c,
            "dtype": str(df[c].dtype),
            "pct_non_null": round(100 * df[c].notna().mean(), 1),
            "description": DESCRIPTIONS.get(c, "TODO: undocumented -- add to DESCRIPTIONS in build_modeling_dataset.py"),
        })
    pd.DataFrame(rows).to_csv(out_path, index=False)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="schools_features.csv",
                         help="Output of build_features.py")
    parser.add_argument("--version", default="v1", help="Freeze version tag, e.g. v1, v2")
    parser.add_argument("--outdir", default=".", help="Directory to write outputs into")
    args = parser.parse_args()

    df = pd.read_csv(args.path, low_memory=False)
    print(f"Loaded {args.path}: {len(df):,} rows x {len(df.columns)} cols")

    print("\nApplying cleaning freeze:")
    df = apply_sentinel_scrub(df)
    check_winsorized(df)
    df = restrict_to_hs_universe(df)
    df = apply_min_size_freeze(df)

    date_tag = dt.date.today().isoformat()
    out_csv = os.path.join(args.outdir, f"modeling_dataset_{args.version}_{date_tag}.csv")
    dict_csv = os.path.join(args.outdir, "data_dictionary_modeling_dataset.csv")

    df.to_csv(out_csv, index=False)
    print(f"\nWrote {out_csv}  ({df.shape[0]:,} rows x {df.shape[1]} cols)")
    write_data_dictionary(df, dict_csv)

    print(f"\n[sector mix, frozen] {dict(df['sector'].value_counts())}")
