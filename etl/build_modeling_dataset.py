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
import re
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

# Same 8-field schema as docs/data_dictionary_schools_org_enriched.csv (variable,
# data_type, source_dataset, grain, vintage_as_of, vintage_confidence, description,
# notes) so the two dictionaries read as one system -- that CSV covers the 127 raw
# joined-table columns; this one covers the ~30 columns build_features.py derives
# on top of it, which weren't documented anywhere before this pass. `data_type` and
# `range`/`pct_non_null` are computed from the actual data at runtime, not hardcoded
# here (see write_data_dictionary).
NU_EXPORT_VINTAGE = ("File exported 2026-06-24 (from source filename timestamp) -- "
                     "no per-variable vintage stated inside the file itself")
NU_EXPORT_CONF = "confirmed (export date only)"

# (source_dataset, grain, vintage_as_of, vintage_confidence, description)
METADATA = {
    "ceeb": ("Sheng's combined schools export", "school",
             "UC Boulder source last updated 2025-01-06 upstream; unclear if Sheng used this exact version",
             "inferred", "College Board CEEB code (join key back to schools_org_all)"),
    "school_name": ("Sheng's combined schools export / NU org export", "school",
                    "not confirmed in repo -- ask Sheng which pull year", "inferred",
                    "School name, school-side if matched else NU org name"),
    "state": ("Sheng's combined schools export", "school",
              "not confirmed in repo -- ask Sheng", "inferred", "State abbreviation"),
    "latitude": ("NU org export", "school", NU_EXPORT_VINTAGE, NU_EXPORT_CONF,
                "School latitude, for location-based clustering (Section 4.4)"),
    "longitude": ("NU org export", "school", NU_EXPORT_VINTAGE, NU_EXPORT_CONF,
                 "School longitude, for location-based clustering (Section 4.4)"),
    "us_region": ("NU org export", "school", NU_EXPORT_VINTAGE, NU_EXPORT_CONF,
                 "NU-assigned US region bucket (South/West/Midwest/Northeast/Illinois) -- "
                 "region peer-group key for performance benchmarking (Section 4.5)"),
    "is_school_match": ("Derived in build_features.py", "school", "n/a (derived flag)", "derived",
                        "True if row matched both a school-side record and an NU org record"),
    "is_public_hs": ("Derived in build_features.py", "school", "n/a (derived flag)", "derived",
                     "True if school-side record present and school_level in {High, Secondary}"),
    "is_private_hs": ("Derived in build_features.py", "school", "n/a (derived flag)", "derived",
                      "True if NU-flagged private type OR has a school-side pss_id, and not public "
                      "-- fixed 2026-07-17, previously excluded pss_id-only rows (see EDA update)"),
    "sector": ("Derived in build_features.py", "school", "n/a (derived flag)", "derived",
               "public / private / other-oos -- other-oos rows are excluded from modeling_dataset"),
    "has_nu_analytics": ("NU org export", "school", NU_EXPORT_VINTAGE, NU_EXPORT_CONF,
                         "True if nu_avg_num_ap_tests_taken or nu_avg_freshman_sat is present"),
    "has_nu_data": ("NU org export", "school", NU_EXPORT_VINTAGE, NU_EXPORT_CONF,
                    "True if row matched any NU org record (nu_guid present) -- broader than has_nu_analytics"),
    "socio_need_index": ("NU org export (Landscape-lineage, per EDA 3a)", "school", NU_EXPORT_VINTAGE, "inferred",
                         "Mean of 5 NU socio need percentiles (higher = more disadvantage; reverse-coded)"),
    **{
        f"{s}_{suffix}": (
            "NU org export (Landscape-lineage, per EDA 3a)", "school", NU_EXPORT_VINTAGE, "inferred",
            f"{'Raw' if suffix == 'need' else 'Reverse-coded (100 - raw)'} NU {s.replace('_', ' ')} percentile "
            f"-- raw is need-coded (high = worse), verified against external Census data (r=-0.60 vs "
            f"county median income); {'kept for reference' if suffix == 'need' else 'advantage-oriented, use this one for modeling'}"
        )
        for s in ["crime_risk", "educational_attainment", "family_stability", "housing_stability", "median_family_income"]
        for suffix in ["need", "adv"]
    },
    "ap_offered": ("CRDC (SY2021-22) + NU org export (undated) -- see ap_intensity_src for per-row provenance",
                   "school", "mixed, see ap_intensity_src", "mixed",
                   "1 if any AP signal present (CRDC offered/enrollment or NU tests taken/offered)"),
    "ap_tests_taken": ("NU org export", "school", NU_EXPORT_VINTAGE, NU_EXPORT_CONF,
                       "NU avg AP tests taken per student (Goal 8, direct measure)"),
    "ap_participation": ("CRDC", "school", "School Year 2021-2022", "confirmed",
                        "CRDC AP enrollment / enrollment_9_12, winsorized 1/99pct (Goal 8, fallback measure)"),
    "ap_intensity_src": ("Derived in build_features.py", "school", "n/a (derived flag)", "derived",
                        "Provenance of the best available AP intensity signal for this row"),
    "ap_score_nu": ("NU org export", "school", NU_EXPORT_VINTAGE, NU_EXPORT_CONF,
                    "NU avg AP EXAM score, 1-5 scale (~35% coverage) -- the performance signal the "
                    "literature (Geiser & Santelices) says carries the outcome signal, vs availability. "
                    "Recruiting-selection biased, skews affluent"),
    "ap_pct_students_nu": ("NU org export", "school", NU_EXPORT_VINTAGE, NU_EXPORT_CONF,
                           "NU pct of students taking any AP -- AP participation breadth (distinct from "
                           "tests-per-student intensity)"),
    "ap_tests_offered": ("NU org export", "school", NU_EXPORT_VINTAGE, NU_EXPORT_CONF,
                         "NU avg # distinct AP tests offered by the school (denominator of ap_take_rate)"),
    "ap_take_rate": ("Derived in build_features.py (NU org export)", "school", NU_EXPORT_VINTAGE, "derived",
                     "AP tests taken / AP tests offered, winsorized 1/99pct -- the 'of 25 offered they took "
                     "5' challenge-seeking ratio (Bob, Wk5 meeting); higher = students engage more of what's "
                     "available"),
    "dual_enrollment_offered": ("CRDC", "school", "School Year 2021-2022", "confirmed",
                               "1 if CRDC reports the school offers dual enrollment"),
    "dual_enrollment_rate": ("CRDC", "school", "School Year 2021-2022", "confirmed",
                             "CRDC dual enrollment / enrollment_9_12, winsorized 1/99pct -- distinct "
                             "CRDC advanced-coursework indicator from AP, per report section 4.1"),
    "testtaker_rate": ("CRDC", "school", "School Year 2021-2022", "confirmed",
                       "CRDC SAT/ACT takers / enrollment_9_12, winsorized 1/99pct (Goal 6)"),
    "sat_participation_nu": ("NU org export", "school", NU_EXPORT_VINTAGE, NU_EXPORT_CONF,
                            "NU pct of seniors taking SAT (Goal 6)"),
    "sat_score_nu": ("NU org export", "school", NU_EXPORT_VINTAGE, NU_EXPORT_CONF,
                     "NU avg freshman SAT score -- NOTE recruiting-selection biased, not a random sample"),
    "act_composite_il": ("ISBE ACT (grade 11 school report card)", "school",
                         "not confirmed in repo -- ask Sheng which ISBE report-card year", "inferred",
                         "Mean of ISBE grade-11 ACT ELA/Math/Science average scores -- IL only, thin "
                         "(~660 schools); standardized-test performance signal for cross-school comparison"),
    "grad_rate_2021": ("EDFacts", "school", "School Year 2020-2021", "confirmed",
                       "Four-year adjusted cohort graduation rate"),
    "frl_rate": ("Sheng's combined schools export (NCES CCD)", "school",
                "not confirmed in repo -- ask Sheng", "inferred",
                "Free/reduced lunch students / total_enrollment, percent"),
    "enrollment_9_12": ("Sheng's combined schools export (NCES CCD)", "school",
                       "not confirmed in repo -- ask Sheng", "inferred",
                       "Grades 9-12 headcount (denominator for AP/SAT rates and the min-size freeze)"),
    **{
        f"grade_{n}": ("Sheng's combined schools export (NCES CCD)", "school",
                      "not confirmed in repo -- ask Sheng", "inferred",
                      f"Grade {n} headcount (Goal 5 pipeline)")
        for n in [9, 10, 11, 12]
    },
    "child_poverty_saipe": ("Census SAIPE (attached at county level in Sheng's export)", "county",
                           "not confirmed in repo -- ask Sheng which SAIPE release year", "inferred",
                           "County-level SAIPE child poverty percent (r=0.89 with ACS, kept as the single poverty proxy)"),
    "per_pupil_state_local": ("ISBE finance", "district (IL only)",
                              "not confirmed in repo -- ask Sheng which ISBE report-card year", "inferred",
                              "IL ISBE true per-pupil state+local expenditure (IL only, ~2.8% coverage)"),
    "leaid": ("Derived in build_features.py from nces_id_12[:7]", "district",
             "n/a (derived key)", "derived",
             "District ID -- NOT the leaid column shipped in schools_org_all, which is 5 chars and "
             "0% match rate against Census finance data; fixed 2026-07-17, see build_funding()"),
    "district_total_revenue": ("Census F-33 (census_school_finances_FY2024_alldistricts.xlsx)", "district",
                               "FY2024", "confirmed (filename)",
                               "District total revenue, dollars (raw units, from $1,000s source)"),
    "per_resident_child_funding_total": ("Census F-33 (FY2024) / SAIPE (2024)", "district",
                                        "FY2024 finance / 2024 SAIPE", "confirmed (filename)",
                                        "F-33 total revenue / SAIPE school-age (5-17) population, winsorized -- "
                                        "a per-resident-child PROXY, not true per-pupil expenditure (Goal 4, national)"),
    "per_resident_child_funding_state_local": ("Census F-33 (FY2024) / SAIPE (2024)", "district",
                                               "FY2024 finance / 2024 SAIPE", "confirmed (filename)",
                                               "Same as per_resident_child_funding_total, state+local revenue only "
                                               "(excludes federal)"),
    "funding_source": ("Derived in build_features.py", "school", "n/a (derived flag)", "derived",
                      "Which funding figure is populated for this row: isbe_il_true_per_pupil / "
                      "census_f33_per_resident_child_proxy / none"),
    "percent_going_to_college_mid": ("NU org export", "school", NU_EXPORT_VINTAGE, NU_EXPORT_CONF,
                                     "NU bucketed percent going to any college, parsed to bucket midpoint"),
    "percent_going_to_4yr_college_mid": ("NU org export", "school", NU_EXPORT_VINTAGE, NU_EXPORT_CONF,
                                         "NU bucketed percent going to 4-year college, parsed to bucket midpoint"),
    "percent_federal_lunch_aid_mid": ("NU org export", "school", NU_EXPORT_VINTAGE, NU_EXPORT_CONF,
                                      "NU bucketed percent on federal lunch aid, parsed to bucket midpoint"),
    "percent_first_gen_college_mid": ("NU org export", "school", NU_EXPORT_VINTAGE, NU_EXPORT_CONF,
                                      "NU bucketed percent first-gen college, parsed to bucket midpoint"),
    "number_of_ap_classes_offered_mid": ("NU org export", "school", NU_EXPORT_VINTAGE, NU_EXPORT_CONF,
                                        "NU bucketed count of AP classes offered, parsed to bucket midpoint"),
    "size_of_senior_class_mid": ("NU org export", "school", NU_EXPORT_VINTAGE, NU_EXPORT_CONF,
                                 "NU bucketed senior class size, parsed to bucket midpoint"),
    "ap_capstone": ("NU org export", "school", NU_EXPORT_VINTAGE, NU_EXPORT_CONF,
                   "1 if NU flags this as an AP Capstone school"),
    "setting": ("NU org export, falling back to NCES locale", "school", "mixed", "mixed",
               "Urban/suburban/rural setting"),
    "ib_flag_candidate": ("IB scraper (data/IB/scrapers) fuzzy-matched in combine_schools.py", "school",
                          "IB scraper pull date not confirmed in repo", "inferred",
                          "1 if IB fuzzy-matched AND match tier is 'review' (never auto_accept nationwide -- "
                          "still needs human confirmation; gating added 2026-07-17, see build_features.py)"),
    "ib_programme_count": ("IB scraper (data/IB/scrapers)", "school",
                          "IB scraper pull date not confirmed in repo", "inferred",
                          "Count of distinct IB programmes offered (PYP/MYP/DP/CP), gated the same way as "
                          "ib_flag_candidate (review-tier match only) -- null for non-candidate rows, not 0"),
    "meets_min_size": ("Derived in build_modeling_dataset.py", "school", "n/a (derived flag)", "derived",
                       f"True if enrollment_9_12 >= {MIN_ENROLLMENT_9_12} or enrollment_9_12 is unknown "
                       f"(freeze gate)"),
    "ap_qualifying_density": ("Derived in build_modeling_dataset.py (NU org export)", "school",
                              NU_EXPORT_VINTAGE, "derived",
                              "Expected AP exams scoring 3+ per student = ap_tests_taken x P(score>=3), "
                              "with P from a normal approximation on ap_score_nu (within-school SD~1.2, "
                              "continuity-corrected cut at 2.5). Winsorized at the 99th pct. Replaces the "
                              "raw mean exam score as the v4 AP-performance signal: a mean rewards "
                              "gatekeeping (sit only your strongest students, post a high mean), density "
                              "credits breadth x success. See docs/RIGOR_SCENARIOS.md scenario B"),
    "ib_intensity_v2": ("CRDC (SY2021-22) + adjudicated IB crosswalk", "school",
                        "CRDC SY2021-22; IB scraper pull date not confirmed in repo", "mixed",
                        "IB participation intensity = crdc_ib_enrollment / enrollment_9_12 where CRDC "
                        "reports it (n~820), else the verified binary ib_flag_v2 (docs/IB_RESCUE.md). "
                        "Clipped to [0, 1]. The v4 replacement for the never-confirmed ib_flag_candidate; "
                        "enters the crdc_coursework component rather than a standalone IB component"),
    "ib_flag_v2": ("Adjudicated IB crosswalk (docs/IB_RESCUE.md; llm_adjudicate_matches.py)", "school",
                   "IB scraper pull date not confirmed in repo; match adjudication is the 2026-07 pass",
                   "verified (human/LLM-adjudicated match)",
                   "Verified binary IB flag: 1 if the school is a confirmed IB World School per the "
                   "human/LLM-adjudicated crosswalk (docs/IB_RESCUE.md), else 0. The trustworthy replacement "
                   "for the never-confirmed ib_flag_candidate; is the fallback signal inside ib_intensity_v2 "
                   "when CRDC IB enrollment is absent"),
    "crdc_ib_enrollment": ("CRDC (SY2021-22)", "school", "School Year 2021-2022", "confirmed",
                           "Count of students enrolled in IB programs as reported by CRDC. Numerator of "
                           "ib_intensity_v2 where present; the CRDC IB item is sparsely populated (~2.6% "
                           "coverage), which is why ib_intensity_v2 falls back to the verified ib_flag_v2"),
}

# --- v4 rigor features -------------------------------------------------------
# Both are the changes adopted in docs/RIGOR_SCENARIOS.md (scenarios A + B) and used by
# build_rigor_classification.py --spec v4. Derived here, at the freeze, so the modeling
# dataset carries them and the index stays a pure scoring step over frozen columns.
AP_SCORE_QUALIFYING_CUT = 2.5   # continuity-corrected boundary for a discrete 1-5 exam score
AP_SCORE_WITHIN_SCHOOL_SD = 1.2  # documented approximation -- College Board publishes no
                                 # per-school score distributions; see RIGOR_SCENARIOS.md
AP_DENSITY_WINSOR_PCT = 0.99
IB_INTENSITY_WINSOR_PCT = 0.99


IB_V2_SOURCE = "schools_combined_enriched_ceeb.csv"
# ib_flag_v2_source (provenance of ib_flag_v2) was carried through v4_2026-07-24 and
# documented in the dictionary, then accidentally dropped in v4_2026-08-01. Restored here
# (2026-08-10) so the frozen dataset matches its dictionary again; aggregated with max()
# like the other rescued columns (any confirmed source wins).
IB_V2_COLS = ["ib_flag_v2", "crdc_ib_enrollment", "ib_flag_v2_source"]


def _ceeb_key(s):
    return pd.to_numeric(s, errors="coerce").astype("Int64").astype(str).replace("<NA>", np.nan)


def attach_ib_v2(df, input_path):
    """Join the rescued IB columns (docs/IB_RESCUE.md) if they aren't already present.

    build_features.py runs off schools_org_all.csv and never sees these two columns -- they
    are produced further up, in combine_schools.py, and land in schools_combined_enriched_ceeb.
    Without this join `ib_intensity_v2` silently comes out empty and the v4 crdc_coursework
    component quietly loses its IB signal, so the join is explicit and its match rate reported.

    `ceeb` is the only key the two frames share, and it is not unique in the source
    (19,084 rows over 16,865 distinct CEEBs), so values are aggregated per CEEB with max --
    "any confirmed IB signal wins", the conservative reading for a rescued flag.
    """
    if all(c in df.columns for c in IB_V2_COLS):
        print(f"  [ib_v2] {IB_V2_COLS} already present -- no join needed")
        return df
    src_path = os.path.join(os.path.dirname(os.path.abspath(input_path)), IB_V2_SOURCE)
    if not os.path.exists(src_path):
        print(f"  [ib_v2] WARNING: {IB_V2_SOURCE} not found next to {input_path} -- "
              f"ib_intensity_v2 will be empty and the v4 index will lose its IB signal.")
        return df

    src = pd.read_csv(src_path, low_memory=False)[["ceeb"] + IB_V2_COLS].copy()
    src["_k"] = _ceeb_key(src["ceeb"])
    n_rows, n_keys = src["_k"].notna().sum(), src["_k"].nunique()
    agg = (src.dropna(subset=["_k"]).groupby("_k")[IB_V2_COLS].max().reset_index())

    df = df.copy()
    df["_k"] = _ceeb_key(df["ceeb"])
    df = df.merge(agg, on="_k", how="left").drop(columns="_k")
    matched = df["ib_flag_v2"].notna().sum()
    print(f"  [ib_v2] joined from {IB_V2_SOURCE} on ceeb "
          f"({n_rows:,} source rows over {n_keys:,} distinct CEEBs, aggregated with max): "
          f"{matched:,}/{len(df):,} rows ({100*matched/len(df):.1f}%) carry a definitive IB flag")
    return df


def derive_rigor_v4_features(df):
    """ap_qualifying_density (scenario B) and ib_intensity_v2 (scenario A)."""
    from scipy.stats import norm

    taken = pd.to_numeric(df.get("ap_tests_taken"), errors="coerce")
    mean_score = pd.to_numeric(df.get("ap_score_nu"), errors="coerce")
    p_qualify = 1 - norm.cdf((AP_SCORE_QUALIFYING_CUT - mean_score) / AP_SCORE_WITHIN_SCHOOL_SD)
    density = taken * pd.Series(p_qualify, index=df.index)
    cap = density.quantile(AP_DENSITY_WINSOR_PCT)
    n_capped = int((density > cap).sum())
    df["ap_qualifying_density"] = density.clip(upper=cap)
    print(f"  [v4] ap_qualifying_density: {df['ap_qualifying_density'].notna().sum():,} schools, "
          f"winsorized at p{AP_DENSITY_WINSOR_PCT:.0%}={cap:.3f} ({n_capped} capped)")

    ib_enr = pd.to_numeric(df.get("crdc_ib_enrollment"), errors="coerce")
    enr = pd.to_numeric(df.get("enrollment_9_12"), errors="coerce")
    ratio = (ib_enr / enr).replace([np.inf, -np.inf], np.nan)
    # CRDC IB enrollment is a headcount of IB-enrolled students that can exceed the 9-12
    # denominator (whole-school IB programmes, middle-grade IB students counted in, stale
    # enrollment): 9 schools land above 1.0. Winsorize the ratio itself before the fallback,
    # so those stay the most-intense schools without a >100% share. The binary fallback is
    # applied after, so a flag-only school keeps a clean 1.0.
    ratio = ratio.clip(upper=ratio.quantile(IB_INTENSITY_WINSOR_PCT))
    flag = pd.to_numeric(df.get("ib_flag_v2"), errors="coerce")
    df["ib_intensity_v2"] = ratio.fillna(flag)
    print(f"  [v4] ib_intensity_v2: {df['ib_intensity_v2'].notna().sum():,} schools "
          f"({ratio.notna().sum():,} from CRDC enrollment share, rest from the verified binary flag)")
    return df


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


def _observed_range(s):
    """Numeric -> 'min – max'; low-cardinality categorical/bool -> value list; else n/a."""
    s = s.dropna()
    if s.empty:
        return "n/a (all null)"
    if pd.api.types.is_numeric_dtype(s) or pd.api.types.is_bool_dtype(s):
        try:
            return f"{s.min():g} - {s.max():g}"
        except TypeError:
            pass
    uniques = s.unique()
    if len(uniques) <= 8:
        return ", ".join(sorted(str(v) for v in uniques))
    return f"{len(uniques)} distinct values"


def write_data_dictionary(df, out_path):
    rows = []
    missing_metadata = []
    for c in df.columns:
        meta = METADATA.get(c)
        if meta is None:
            missing_metadata.append(c)
            source_dataset, grain, vintage_as_of, vintage_confidence, description = (
                "TODO: undocumented", "unknown", "unknown", "undocumented",
                "TODO: add to METADATA in build_modeling_dataset.py")
        else:
            source_dataset, grain, vintage_as_of, vintage_confidence, description = meta
        rows.append({
            "variable": c,
            "data_type": str(df[c].dtype),
            "source_dataset": source_dataset,
            "grain": grain,
            "vintage_as_of": vintage_as_of,
            "vintage_confidence": vintage_confidence,
            "range": _observed_range(df[c]),
            "pct_non_null": round(100 * df[c].notna().mean(), 1),
            "description": description,
        })
    if missing_metadata:
        print(f"  [dictionary] WARNING: no METADATA entry for {missing_metadata} -- "
              f"add them to build_modeling_dataset.py")
    pd.DataFrame(rows).to_csv(out_path, index=False)
    print(f"\nWrote {out_path}")


# ---------------------------------------------------------------------------
# Review flag (2026-08-10, from the 8/3 client note on correctional facilities).
# Additive boolean column that IDENTIFIES -- but never drops -- correctional
# facilities. It is not a model feature, so rigor and clustering are unchanged;
# downstream can filter on it once NU signs off on excluding this population.
# (The other 8/3 CEEB items -- generic/placeholder codes -- live entirely in the
# missing-schools/matching layer: none survive the HS-universe + min-size freeze,
# so they never reach this dataset. See csv_exports/review_generic_ceeb_codes.csv.)
# ---------------------------------------------------------------------------
CORRECTIONAL_RE = (
    r"correction|juvenile|detention|penitentiary|reformatory|"
    r"youth (?:center|facility|services)|juvenile hall|\bjail\b|\bprison\b|"
    r"justice center|secure (?:care|facility)"
)


def flag_review_cases(df):
    """Flag correctional facilities (8/3 notes item 5) -- flagged, not dropped."""
    name = df["school_name"].fillna("").astype(str)
    df["is_correctional_facility"] = name.str.contains(CORRECTIONAL_RE, case=False, regex=True)
    print(f"  [review flags] {int(df['is_correctional_facility'].sum())} correctional facilities "
          f"flagged (not dropped)")
    return df


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

    print("\nDeriving v4 rigor features:")
    df = attach_ib_v2(df, args.path)
    df = derive_rigor_v4_features(df)

    print("\nFlagging review cases (8/3 notes):")
    df = flag_review_cases(df)

    date_tag = dt.date.today().isoformat()
    out_csv = os.path.join(args.outdir, f"modeling_dataset_{args.version}_{date_tag}.csv")
    dict_csv = os.path.join(args.outdir, "data_dictionary_modeling_dataset.csv")

    df.to_csv(out_csv, index=False)
    print(f"\nWrote {out_csv}  ({df.shape[0]:,} rows x {df.shape[1]} cols)")
    write_data_dictionary(df, dict_csv)

    print(f"\n[sector mix, frozen] {dict(df['sector'].value_counts())}")
