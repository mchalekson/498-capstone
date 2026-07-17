"""
build_features.py  —  feature engineering + validation for schools_org_all / schools_org_enriched

Turns the joined table (Sheng's public-school export + Bob's NU org export, joined on CEEB)
into a modeling-ready feature frame, and prints a validation report that catches the
issues found in EDA: the need-coded socio indices (sign flip), the CEEB fan-out dup rows,
and the private-school sector misclassification that was hiding the IB flag.

Designed to plug into the pipeline as a feature step; it does NOT own the final cleaning
freeze (that's the build_modeling_dataset.py step). Run:

    python build_features.py schools_org_all.csv

By default this also looks for census_school_finances_clean.csv and
census_saipe_poverty_clean.csv next to the input file (Goal 4 funding join — see
build_funding()). Pass --no-funding to skip if those files aren't available.
"""
import argparse, os, re, warnings
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


def build_funding(out, df, finance_df, saipe_df):
    """
    Goal 4 — national per-student funding via Census F-33 district finance,
    joined on LEAID (district ID), as a national overlay on top of the
    existing IL-only ISBE per-pupil figure.

    LEAID here is derived from nces_id_12[:7], NOT the 'leaid' column that
    ships in schools_org_all: that column is only 5 characters (truncated
    from the 12-digit NCESSCH some other way upstream) and has a **0% match
    rate** against census_school_finances_clean.leaid. The standard LEAID is
    the first 7 characters of the 12-digit NCESSCH (2-digit state FIPS +
    5-digit district ID) — using nces_id_12[:7] gets an 87% match rate on
    the ~23k rows that carry a 12-digit ID (verified directly against
    census_school_finances_clean before wiring this up). This was the
    "crosswalk blocker" noted in views.sql, which predates the 12-digit
    ELSI re-pull and only applies to the old nces_public_schools_clean table.

    IMPORTANT CAVEAT: F-33 has no enrollment/membership field, and no
    verified district-level enrollment source is loaded in this pipeline
    yet (nces_public_schools_clean's own leaid is the same kind of stale,
    unverifiable truncation, so it can't be used to aggregate school-level
    enrollment up to the district). So "per student" here is NOT true
    per-pupil expenditure — it's total_revenue divided by SAIPE's
    school-age (5-17) population estimate for the district, a standard
    Census companion pairing but a proxy for enrollment, not a headcount of
    actual enrolled students. Do not report this as equivalent to the IL
    ISBE per-pupil figure (which IS a true per-pupil number) without that
    caveat attached.
    """
    leaid7 = df["nces_id_12"].astype(str).str.strip().str[:7].where(df["nces_id_12"].notna())
    out["leaid"] = leaid7

    fin = finance_df.set_index("leaid")
    sai = saipe_df.set_index("leaid")

    total_rev = pd.to_numeric(leaid7.map(fin["total_revenue_000s"]), errors="coerce") * 1000
    fed_rev = pd.to_numeric(leaid7.map(fin["federal_revenue_000s"]), errors="coerce") * 1000
    state_local_rev = total_rev - fed_rev
    child_pop = pd.to_numeric(leaid7.map(sai["child_population_5_17"]), errors="coerce")

    out["district_total_revenue"] = total_rev
    out["per_resident_child_funding_total"] = winsorize(
        np.where(child_pop > 0, total_rev / child_pop, np.nan))
    out["per_resident_child_funding_state_local"] = winsorize(
        np.where(child_pop > 0, state_local_rev / child_pop, np.nan))
    out["funding_source"] = np.select(
        [out["per_pupil_state_local"].notna(), out["per_resident_child_funding_state_local"].notna()],
        ["isbe_il_true_per_pupil", "census_f33_per_resident_child_proxy"], default="none")
    return out


def build(df, finance_df=None, saipe_df=None):
    out = pd.DataFrame(index=df.index)
    num = lambda c: pd.to_numeric(df[c], errors="coerce")

    # ---- identity / universe -------------------------------------------------
    out["ceeb"] = df["ceeb"].fillna(df["nu_ceeb"])
    out["school_name"] = df["school_name"].fillna(df["nu_name"])
    out["state"] = df["state"]
    out["latitude"] = num("nu_latitude")    # NU-sourced; coverage tracks has_nu_data
    out["longitude"] = num("nu_longitude")
    out["is_school_match"] = df["school_id"].notna() & df["nu_guid"].notna()
    out["is_public_hs"] = df["school_id"].notna() & df["school_level"].isin(["High", "Secondary"])
    # is_private_hs must also catch rows with a school-side record (pss_id) but no NU
    # org match: school_level is null-by-construction for every pss_id row in Sheng's
    # export (it's a public-only field), so the original `school_id.isna()` requirement
    # silently dropped all 1,354 private schools that DO have a school-side row -- which
    # is exactly where the IB matches (ib_school_id) live. Without this fix those schools
    # fell into "other/oos" and were invisible to every coverage check below.
    out["is_private_hs"] = (
        df["nu_type"].isin(["Private Religiously Affiliated", "Private Secular"])
        | df["pss_id"].notna()
    ) & ~out["is_public_hs"]
    out["sector"] = np.where(out["is_public_hs"], "public",
                     np.where(out["is_private_hs"], "private", "other/oos"))
    out["has_nu_analytics"] = num("nu_avg_num_ap_tests_taken").notna() | num("nu_avg_freshman_sat").notna()
    out["has_nu_data"] = df["nu_guid"].notna()   # broader stratum: matched ANY NU org record

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

    # ---- CRDC advanced-coursework indicator beyond AP (dual enrollment) -------
    out["dual_enrollment_offered"] = (num("crdc_dual_enr_offered") == 1).astype("Int64")
    out["dual_enrollment_rate"] = winsorize(np.where(enr > 0, num("crdc_dual_enrollment") / enr, np.nan))

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

    # ---- funding (Goal 4): IL ISBE true per-pupil + national F-33 proxy overlay --
    out["per_pupil_state_local"] = num("total_per_pupil_expenditures_state_local")  # IL only, true per-pupil
    if finance_df is not None and saipe_df is not None:
        out = build_funding(out, df, finance_df, saipe_df)
    else:
        out["leaid"] = df["nces_id_12"].astype(str).str[:7].where(df["nces_id_12"].notna())

    # ---- ordinal buckets -> midpoints ----------------------------------------
    for c in ORDINAL_COLS:
        if c in df:
            out[c.replace("nu_", "") + "_mid"] = df[c].map(parse_bucket_midpoint)

    # ---- categorical / flags --------------------------------------------------
    out["ap_capstone"] = (df["nu_ap_capstone_school"] == "Yes").astype("Int64")
    out["setting"] = df["nu_setting"].fillna(df["locale"])
    # Gated on match tier: ib_match_tier is nationwide fuzzy-name matching with no
    # state to block on (see combine_schools.py), so nothing is ever auto_accept --
    # "review" (588 rows) means a real candidate pending human confirmation, "reject"
    # (766 rows) means the best candidate still scored too low to trust. Treating
    # ib_school_id.notna() as a flag (the old behavior) silently counted the 766
    # rejects as confirmed IB schools.
    out["ib_flag_candidate"] = (
        df["ib_school_id"].notna() & (df["ib_match_tier"] == "review")
    ).astype("Int64")
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
          f"  {'!! CEEB not unique on school side -- see EDA_features_joined.md 3b' if dups else 'OK'}")

    # 3) coverage among public-HS universe (national, CRDC-extendable)
    pub = feats[feats["is_public_hs"]]
    print(f"\n[coverage] public-HS universe n={len(pub)}")
    for c in ["ap_offered", "ap_tests_taken", "ap_participation", "testtaker_rate",
              "grad_rate_2021", "frl_rate", "socio_need_index", "per_pupil_state_local",
              "per_resident_child_funding_state_local"]:
        if c not in pub.columns:
            continue  # funding join skipped (--no-funding)
        cov = (pub[c] == 1).mean() if c == "ap_offered" else pub[c].notna().mean()
        print(f"   {c:38} {100*cov:5.1f}%")

    # 4) coverage among private-HS universe (nu-only + the pss_id-matched slice)
    priv = feats[feats["is_private_hs"]]
    print(f"\n[coverage] private-HS universe n={len(priv)}")
    for c in ["has_nu_data", "has_nu_analytics"]:
        print(f"   {c:38} {100*priv[c].mean():5.1f}%")

    # 5) IB — gated on match tier, reported across BOTH sectors (all real matches are
    # private schools; reporting only within is_public_hs, as the old validate() did,
    # always showed ~0% and made the join look broken when it was a sector-filter bug)
    hs = feats[feats["is_public_hs"] | feats["is_private_hs"]]
    ib_rate = hs["ib_flag_candidate"].eq(1).mean()
    ib_rate_priv = priv["ib_flag_candidate"].eq(1).mean() if len(priv) else float("nan")
    print(f"\n[IB]    ib_flag_candidate rate, public+private HS universe (n={len(hs)}): {100*ib_rate:5.1f}%")
    print(f"        ib_flag_candidate rate, private-HS only (n={len(priv)}):          {100*ib_rate_priv:5.1f}%")

    # 6) funding source mix (Goal 4)
    if "funding_source" in feats.columns:
        print(f"\n[funding source mix] {dict(feats['funding_source'].value_counts())}")

    print(f"\n[sector mix] {dict(feats['sector'].value_counts())}")


def _load_funding_inputs(input_path, no_funding):
    if no_funding:
        return None, None
    base = os.path.dirname(os.path.abspath(input_path))
    fin_path = os.path.join(base, "census_school_finances_clean.csv")
    sai_path = os.path.join(base, "census_saipe_poverty_clean.csv")
    if not (os.path.exists(fin_path) and os.path.exists(sai_path)):
        print(f"[funding] census_school_finances_clean.csv / census_saipe_poverty_clean.csv "
              f"not found next to {input_path} -- skipping Goal 4 funding join (pass --no-funding "
              f"to silence this).")
        return None, None
    finance_df = pd.read_csv(fin_path, dtype={"leaid": str}, low_memory=False)
    saipe_df = pd.read_csv(sai_path, dtype={"leaid": str}, low_memory=False)
    return finance_df, saipe_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="schools_org_all.csv")
    parser.add_argument("--no-funding", action="store_true",
                         help="Skip the Goal 4 Census F-33/SAIPE funding join")
    args = parser.parse_args()

    df = pd.read_csv(args.path, low_memory=False)
    finance_df, saipe_df = _load_funding_inputs(args.path, args.no_funding)
    feats = build(df, finance_df=finance_df, saipe_df=saipe_df)
    validate(df, feats)
    feats.to_csv("schools_features.csv", index=False)
    print(f"\nWrote schools_features.csv  ({feats.shape[0]} rows x {feats.shape[1]} cols)")
