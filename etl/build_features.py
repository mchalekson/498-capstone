"""
build_features.py  —  feature engineering + validation for schools_org_all / schools_org_enriched

Turns the joined table (Sheng's public-school export + Bob's NU org export, joined on CEEB)
into a modeling-ready feature frame, and prints a validation report that catches the two
issues found in EDA: the need-coded socio indices (sign flip) and the CEEB fan-out dup rows.

Designed to plug into the pipeline as a feature step; it does NOT own the final cleaning
freeze (that's the modeling_dataset.csv step). Run:  python build_features.py schools_org_all.csv
"""
import sys, re, warnings
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")

SOCIO = ["crime_risk", "educational_attainment", "family_stability",
         "housing_stability", "median_family_income"]

ORDINAL_COLS = ["nu_percent_going_to_college", "nu_percent_going_to_4yr_college",
                "nu_percent_federal_lunch_aid", "nu_percent_first_gen_college",
                "nu_number_of_ap_classes_offered", "nu_size_of_senior_class"]


def parse_bucket_midpoint(val):
    """'80-89%' -> 84.5 ; '90% or more' -> 95 ; '10% or fewer' -> 5 ;
       'greater than 20' -> 24 ; 'More than 1000' -> 1200 ; '01 - 02' -> 1.5"""
    if pd.isna(val):
        return np.nan
    s = str(val).lower().replace("%", "").strip()
    nums = [float(n) for n in re.findall(r"\d+\.?\d*", s)]
    if not nums:
        return np.nan
    if len(nums) >= 2:                       # a real range: take the midpoint
        return (nums[0] + nums[1]) / 2
    n = nums[0]                               # open-ended bucket
    if any(w in s for w in ["or more", "greater than", "more than", "over", "plus"]):
        return n * 1.2 if n >= 100 else n + 5
    if any(w in s for w in ["or fewer", "or less", "fewer", "under"]):
        return n / 2
    return n


def winsorize(s, lo=0.01, hi=0.99):
    s = pd.Series(pd.to_numeric(np.asarray(s, dtype="float64"), errors="coerce"))
    ql, qh = s.quantile(lo), s.quantile(hi)
    return s.clip(ql, qh).values


def build(df):
    out = pd.DataFrame(index=df.index)
    num = lambda c: pd.to_numeric(df[c], errors="coerce")

    # ---- identity / universe -------------------------------------------------
    out["ceeb"] = df["ceeb"].fillna(df["nu_ceeb"])
    out["school_name"] = df["school_name"].fillna(df["nu_name"])
    out["state"] = df["state"]
    out["is_school_match"] = df["school_id"].notna() & df["nu_guid"].notna()
    out["is_public_hs"] = df["school_id"].notna() & df["school_level"].isin(["High", "Secondary"])
    out["is_private_hs"] = df["school_id"].isna() & df["nu_type"].isin(
        ["Private Religiously Affiliated", "Private Secular"])
    out["sector"] = np.where(out["is_public_hs"], "public",
                     np.where(out["is_private_hs"], "private", "other/oos"))
    out["has_nu_analytics"] = num("nu_avg_num_ap_tests_taken").notna() | num("nu_avg_freshman_sat").notna()

    # ---- socio context: REVERSE-CODE (raw is need-coded, high = worse) --------
    # verified: nu_median_family_income corr -0.60 with actual county $ income.
    for s in SOCIO:
        c = f"nu_{s}"
        if c in df:
            out[f"{s}_need"] = num(c)                 # keep raw meaning explicit
            out[f"{s}_adv"] = 100 - num(c)            # advantage-oriented for modeling
    need_cols = [f"{s}_need" for s in SOCIO if f"nu_{s}" in df]
    out["socio_need_index"] = out[need_cols].mean(axis=1)   # higher = more disadvantage

    # ---- AP: availability floor + two (distinct!) intensity measures ----------
    out["ap_offered"] = (
        (num("crdc_ap_offered") == 1) |
        (num("crdc_ap_enrollment") > 0) |
        (num("nu_avg_num_ap_tests_taken") > 0) |
        (num("nu_avg_num_ap_tests_offered") > 0)
    ).astype("Int64")
    out["ap_tests_taken"] = num("nu_avg_num_ap_tests_taken")           # avg #tests/student (nu)
    enr = num("enrollment_9_12")
    out["ap_participation"] = winsorize(np.where(enr > 0, num("crdc_ap_enrollment") / enr, np.nan))
    out["ap_intensity_src"] = np.select(
        [out["ap_tests_taken"].notna(), out["ap_participation"].notna(), out["ap_offered"] == 1],
        ["nu_tests_taken", "crdc_participation", "offered_flag_only"], default="none")

    # ---- SAT / ACT ------------------------------------------------------------
    out["testtaker_rate"] = winsorize(np.where(enr > 0, num("crdc_satact_takers") / enr, np.nan))
    out["sat_participation_nu"] = num("nu_pct_seniors_taking_sat")
    out["sat_score_nu"] = num("nu_avg_freshman_sat")                  # NOTE: recruiting-selection biased

    # ---- outcomes / context (national, high coverage) -------------------------
    out["grad_rate_2021"] = num("grad_rate_2021")
    out["frl_rate"] = np.where(num("total_enrollment") > 0,
                               100 * num("frl_students") / num("total_enrollment"), np.nan)
    out["enrollment_9_12"] = enr
    for g in ["grade_9", "grade_10", "grade_11", "grade_12"]:         # Goal 5 pipeline
        out[g] = num(g)
    out["child_poverty_saipe"] = num("county_pct_child_poverty_saipe")  # r=0.89 w/ ACS; keep one

    # ---- funding (Goal 4): IL ISBE present; national F-33 is a TODO via leaid --
    out["per_pupil_state_local"] = num("total_per_pupil_expenditures_state_local")  # IL only for now
    out["leaid"] = df["leaid"]     # LEAID = nces_id_12[:7] -> ready for F-33 join

    # ---- ordinal buckets -> midpoints ----------------------------------------
    for c in ORDINAL_COLS:
        if c in df:
            out[c.replace("nu_", "") + "_mid"] = df[c].map(parse_bucket_midpoint)

    # ---- categorical / flags --------------------------------------------------
    out["ap_capstone"] = (df["nu_ap_capstone_school"] == "Yes").astype("Int64")
    out["setting"] = df["nu_setting"].fillna(df["locale"])
    out["ib_flag"] = df["ib_school_id"].notna().astype("Int64")       # NOTE: currently ~0 on HS rows
    return out


def validate(df, feats):
    print("=" * 72)
    print("VALIDATION REPORT")
    print("=" * 72)

    # 1) socio direction (must stay negative vs actual county $ income)
    a = pd.to_numeric(df["nu_median_family_income"], errors="coerce")
    b = pd.to_numeric(df["county_median_hh_income"], errors="coerce")
    r = a.corr(b)
    flag = "OK (need-coded, reverse handled)" if r < -0.2 else "!! CHECK: direction changed"
    print(f"[socio] corr(nu_median_family_income, county_$ income) = {r:+.2f}  -> {flag}")

    # 2) CEEB fan-out / duplicate org rows
    g = df["nu_guid"].dropna()
    dups = len(g) - g.nunique()
    print(f"[join]  org rows={len(g)}  unique nu_guid={g.nunique()}  DUP org rows={dups}"
          f"  {'!! CEEB not unique on school side' if dups else 'OK'}")

    # 3) coverage among public-HS universe
    pub = feats[feats["is_public_hs"]]
    print(f"\n[coverage] public-HS universe n={len(pub)}")
    for c in ["ap_offered", "ap_tests_taken", "ap_participation", "testtaker_rate",
              "grad_rate_2021", "frl_rate", "socio_need_index", "per_pupil_state_local", "ib_flag"]:
        if c == "ap_offered":
            cov = (pub[c] == 1).mean()
        elif c == "ib_flag":
            cov = (pub[c] == 1).mean()
        else:
            cov = pub[c].notna().mean()
        print(f"   {c:24} {100*cov:5.1f}%")
    print(f"\n[sector mix] {dict(feats['sector'].value_counts())}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "schools_org_all.csv"
    df = pd.read_csv(path, low_memory=False)
    feats = build(df)
    validate(df, feats)
    feats.to_csv("schools_features.csv", index=False)
    print(f"\nWrote schools_features.csv  ({feats.shape[0]} rows x {feats.shape[1]} cols)")
