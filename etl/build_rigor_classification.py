"""
build_rigor_classification.py -- five-tier academic rigor composite (report Section 4.1).

Per the written report (written-report-iterations/MSDS_498_version-wk3.pdf, Section 4.1
"Academic Rigor Classification"): rigor is NOT a supervised label learned from historical
ground truth. It is a transparent, weighted composite index built directly from four named
inputs -- AP course counts/enrollment, IB course counts/enrollment, CRDC's advanced-coursework
indicators, and standardized test participation -- cut into five ordinal tiers (Below Average,
Average, Demanding, Very Demanding, Most Demanding), the same five labels CollegeBoard's
discontinued Landscape tool used for its own curricular-rigor indicator.

The report requires, verbatim:
  - nominal weights (assigned during construction) AND effective weights (what each feature
    actually contributes given its variance/covariance with the others) -- both reported, not
    just one
  - a sensitivity analysis varying the weighting scheme, reporting rank-order correlation and
    the number of schools that change tier
  - a CRDC-available vs. CRDC-unavailable comparison, since CRDC access is not guaranteed
    long-term (see combine_schools.py / report Section 2's "third finding")
  - the correlation between the poverty/funding overlay and the rigor score reported
    explicitly, not presented as an independent enrichment layer (the composite-indicator
    literature the report reviews warns that offerings-based indices tend to reproduce
    socioeconomic ordering)
  - per-school logging of which features were actually available, rather than silent
    imputation or exclusion of incomplete-coverage schools

Component mapping (named inputs -> available columns):
  - AP OPPORTUNITY (offered/taken)  -> ap_tests_taken, number_of_ap_classes_offered_mid,
    ap_take_rate (NU-sourced). "Opportunity structure": what the school offers and how much
    of it students engage. The take-rate is the "of 25 offered they took 5" ratio Bob asked
    for in the Wk5 meeting.
  - AP PERFORMANCE (exam scores)    -> ap_score_nu (NU-sourced, ~35% coverage). ADDED Wk5:
    the literature review's most consequential finding (Geiser & Santelices 2004, sec 2.2)
    is that AP *exam performance*, not course availability, predicts college outcomes -- yet
    the first-pass model was availability-only. This is the performance axis it was missing.
  - IB course counts/enrollment     -> ib_flag_candidate -- EXCLUDED from the default
    weighting (weight 0): the report states IB participation "is not yet a usable rigor-
    classifier input" since no IB match is above 'review' tier. Included only in the
    ib_included sensitivity scenario, to show what changes IF it were trusted.
  - CRDC advanced-coursework        -> ap_participation, dual_enrollment_rate (CRDC-sourced)
  - Standardized test PARTICIPATION -> testtaker_rate (CRDC), sat_participation_nu (NU)
  - Standardized test PERFORMANCE   -> sat_score_nu, act_composite_il. ADDED Wk5, same
    performance-vs-availability rationale: score signal, not just who sat the exam. Both are
    recruiting/IL biased -- see the coverage + selection caveats reported at run time.

NOTE ON COVERAGE BIAS: the two performance components are NU-recruiting-universe sourced
(~35% coverage, skewing affluent). Proportional weight reallocation means uncovered schools
fall back to the opportunity/participation signals -- so a performance-informed tier is only
produced where performance data exists, and the availability_only sensitivity scheme below
quantifies exactly how much the added performance signal moves tiers.

Run:  python build_rigor_classification.py modeling_dataset_v2_2026-07-20.csv --version v3
"""
import argparse
import datetime as dt
import os

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

TIER_LABELS = ["Below Average", "Average", "Demanding", "Very Demanding", "Most Demanding"]

# component -> list of raw columns averaged (after z-scoring) to form that component.
#
# Two specs are kept side by side so the v3 -> v4 change is auditable rather than a silent
# edit. v4 is the default (adopted per docs/RIGOR_SCENARIOS.md, scenarios A + B); pass
# --spec v3 to reproduce the earlier index for comparison.
#
#   v3 -> v4, change 1 (scenario B): ap_performance switches from the raw mean exam score
#   (ap_score_nu) to ap_qualifying_density -- expected exams scoring 3+ per student. A mean
#   rewards gatekeeping: a school that sits only its strongest students posts a high mean and
#   an open-access school is penalised for breadth. Density fuses opportunity x performance
#   and is the College Board's own equity-metric logic. Empirically it cuts the metric's
#   correlation with take-rate from -0.144 to -0.091 and reduces SES confounding.
#
#   v3 -> v4, change 2 (scenario A): the standalone `ib` component (built on the never-
#   confirmed ib_flag_candidate, weight 0 and therefore inert) is replaced by ib_intensity_v2
#   folded into crdc_coursework, where it carries real weight. The flag is the adjudicated,
#   human-verified one from docs/IB_RESCUE.md. This is what makes IB count at all.
COMPONENT_SPECS = {
    "v3": {
        "ap_opportunity": ["ap_tests_taken", "number_of_ap_classes_offered_mid", "ap_take_rate"],
        "ap_performance": ["ap_score_nu"],
        "ib": ["ib_flag_candidate"],
        "crdc_coursework": ["ap_participation", "dual_enrollment_rate"],
        "test_participation": ["testtaker_rate", "sat_participation_nu"],
        "test_performance": ["sat_score_nu", "act_composite_il"],
    },
    "v4": {
        "ap_opportunity": ["ap_tests_taken", "number_of_ap_classes_offered_mid", "ap_take_rate"],
        "ap_performance": ["ap_qualifying_density"],
        "ib": ["ib_flag_candidate"],   # retained only for the ib_included sensitivity scheme
        "crdc_coursework": ["ap_participation", "dual_enrollment_rate", "ib_intensity_v2"],
        "test_participation": ["testtaker_rate", "sat_participation_nu"],
        "test_performance": ["sat_score_nu", "act_composite_il"],
    },
}
DEFAULT_SPEC = "v4"
COMPONENTS = COMPONENT_SPECS[DEFAULT_SPEC]

# nominal weighting schemes to compare in the sensitivity analysis. "designed" is the default
# used for the tier assignment written to the output file; ib excluded per report caveat above.
# The two performance components carry 0.40 combined in the default scheme -- reflecting the
# literature that performance is the stronger signal, without letting a ~35%-coverage feature
# dominate. "availability_only" reproduces the pre-Wk5 model (no performance) so the sensitivity
# table directly answers "how much did adding exam performance move the tiers?"
WEIGHT_SCHEMES = {
    "designed":          {"ap_opportunity": 0.25, "ap_performance": 0.20, "ib": 0.00,
                          "crdc_coursework": 0.20, "test_participation": 0.15, "test_performance": 0.20},
    "equal":             {"ap_opportunity": 0.20, "ap_performance": 0.20, "ib": 0.00,
                          "crdc_coursework": 0.20, "test_participation": 0.20, "test_performance": 0.20},
    "availability_only": {"ap_opportunity": 0.40, "ap_performance": 0.00, "ib": 0.00,
                          "crdc_coursework": 0.35, "test_participation": 0.25, "test_performance": 0.00},
    "performance_heavy": {"ap_opportunity": 0.15, "ap_performance": 0.35, "ib": 0.00,
                          "crdc_coursework": 0.10, "test_participation": 0.10, "test_performance": 0.30},
    "ib_included":       {"ap_opportunity": 0.20, "ap_performance": 0.20, "ib": 0.20,
                          "crdc_coursework": 0.15, "test_participation": 0.10, "test_performance": 0.15},
}
DEFAULT_SCHEME = "designed"


def zscore(s):
    s = pd.to_numeric(s, errors="coerce")
    mu, sd = s.mean(), s.std()
    if not sd or np.isnan(sd):
        return pd.Series(np.nan, index=s.index)
    return (s - mu) / sd


def build_components(df, components=None):
    """z-score each raw sub-feature, then average the available ones per component per row."""
    comp = pd.DataFrame(index=df.index)
    for name, cols in (components or COMPONENTS).items():
        z = pd.DataFrame({c: zscore(df[c]) for c in cols if c in df.columns})
        comp[name] = z.mean(axis=1, skipna=True)  # NaN only if ALL sub-features are missing
    return comp


def weighted_composite(comp, weights):
    """
    Per-row weighted average over only the components available for that row (proportional
    reallocation of weight -- the standard composite-indicator response to missing components,
    rather than imputing a value or dropping the row). Rows with NO available component score
    NaN and are logged as insufficient data, not silently excluded.
    """
    names = list(weights.keys())
    w = pd.Series(weights)
    avail = comp[names].notna()
    w_matrix = avail.mul(w, axis=1)
    w_sum = w_matrix.sum(axis=1)
    weighted_vals = (comp[names].fillna(0) * w_matrix).sum(axis=1)
    score = np.where(w_sum > 0, weighted_vals / w_sum, np.nan)
    return pd.Series(score, index=comp.index), avail


DEFAULT_TIER_METHOD = "natural"


def assign_tiers(score, method=DEFAULT_TIER_METHOD):
    """Cut the composite score into five ordinal tiers.

    Two methods, both reported (the report calls for cut-point sensitivity, not a single
    canonical scheme):
      - "quantile": quintiles of the scored population -- equal-sized buckets. Transparent,
        but the Wk5 client note is explicit that real institution rigor is *not* evenly
        distributed into equal buckets, so this is a default, not a claim about the world.
      - "natural" (DEFAULT): Jenks-style natural breaks via 1-D k-means on the score. Cut-points
        fall at genuine gaps in the score distribution, so tier sizes vary -- which is the
        behaviour the client asked for. Cluster centroids are ordered low->high and mapped onto
        the five labels.
    """
    valid = score.dropna()
    if valid.empty or valid.nunique() < 5:
        return pd.Series(pd.NA, index=score.index, dtype="object"), pd.Series(pd.NA, index=score.index)
    tier_num = pd.Series(pd.NA, index=score.index, dtype="Int64")
    if method == "quantile":
        ranks = valid.rank(pct=True)
        bucket = np.minimum((ranks * 5).astype(int), 4)  # 0..4
        tier_num.loc[valid.index] = bucket.values
    elif method == "natural":
        km = KMeans(n_clusters=5, n_init=10, random_state=42).fit(valid.values.reshape(-1, 1))
        # relabel raw cluster ids so 0=lowest-score cluster ... 4=highest (k-means ids are arbitrary)
        order = np.argsort(km.cluster_centers_.ravel())
        remap = {old: new for new, old in enumerate(order)}
        tier_num.loc[valid.index] = pd.Series(km.labels_, index=valid.index).map(remap).values
    else:
        raise ValueError(f"unknown tier method: {method!r}")
    tier_label = tier_num.map(lambda i: TIER_LABELS[int(i)] if pd.notna(i) else pd.NA)
    return tier_label, tier_num


def effective_weights(comp, weights, full_coverage_mask):
    """
    Standard composite-indicator variance decomposition (nominal vs. effective weight):
    Var(sum_i w_i Z_i) = sum_i sum_j w_i w_j Cov(Z_i, Z_j)
    effective_weight_i = [ sum_j w_i w_j Cov(Z_i, Z_j) ] / Var(composite)

    Computed on the full-coverage subset only (schools with every component present) since
    covariance requires joint observations -- reported alongside the subset size so the
    decomposition's own coverage limitation is visible, not hidden.
    """
    names = [n for n, w in weights.items() if w > 0]
    sub = comp.loc[full_coverage_mask, names]
    if len(sub) < 10 or len(names) < 2:
        return {n: np.nan for n in names}, np.nan, len(sub)
    cov = sub.cov()
    w = pd.Series({n: weights[n] for n in names})
    total_var = float(w @ cov @ w)
    eff = {}
    for i in names:
        contrib = sum(w[i] * w[j] * cov.loc[i, j] for j in names)
        eff[i] = contrib / total_var if total_var else np.nan
    return eff, total_var, len(sub)


def sensitivity_analysis(comp, base_scheme=DEFAULT_SCHEME):
    """Vary the weighting scheme; report Spearman rank correlation vs. the base scheme and the
    number/percent of schools whose assigned tier changes -- exactly what the report asks for."""
    base_score, _ = weighted_composite(comp, WEIGHT_SCHEMES[base_scheme])
    base_tier, _ = assign_tiers(base_score)
    rows = []
    for name, weights in WEIGHT_SCHEMES.items():
        if name == base_scheme:
            continue
        score, _ = weighted_composite(comp, weights)
        tier, _ = assign_tiers(score)
        both = base_score.notna() & score.notna()
        rank_corr = base_score[both].corr(score[both], method="spearman") if both.sum() > 1 else np.nan
        both_tiered = base_tier.notna() & tier.notna()
        n_changed = int((base_tier[both_tiered] != tier[both_tiered]).sum())
        pct_changed = 100 * n_changed / both_tiered.sum() if both_tiered.sum() else np.nan
        rows.append({
            "scheme": name, "vs": base_scheme, "n_compared": int(both_tiered.sum()),
            "spearman_rank_corr": round(rank_corr, 4) if pd.notna(rank_corr) else np.nan,
            "n_schools_changed_tier": n_changed,
            "pct_schools_changed_tier": round(pct_changed, 1) if pd.notna(pct_changed) else np.nan,
        })
    return pd.DataFrame(rows)


def crdc_availability_scenario(comp, df):
    """
    Report's explicit ask: compare tiers computed WITH vs. WITHOUT CRDC-sourced signal
    (crdc_coursework component, and the CRDC half of test_participation), restricted to
    schools where CRDC data actually is available today, so the comparison isolates what
    CRDC's presence changes rather than conflating it with schools that never had it.
    """
    has_crdc = df["ap_participation"].notna() | df["dual_enrollment_rate"].notna() | df["testtaker_rate"].notna()

    with_crdc_weights = WEIGHT_SCHEMES[DEFAULT_SCHEME]
    score_with, _ = weighted_composite(comp, with_crdc_weights)
    tier_with, _ = assign_tiers(score_with)

    # NU-only fallback: drop crdc_coursework, and force test_participation to use NU's
    # sat_participation_nu only by temporarily blanking the CRDC-sourced testtaker_rate
    comp_no_crdc = comp.copy()
    nu_only_test = zscore(df["sat_participation_nu"])
    comp_no_crdc["test_participation"] = nu_only_test
    no_crdc_weights = {"ap_opportunity": 0.30, "ap_performance": 0.25, "ib": 0.00,
                       "crdc_coursework": 0.00, "test_participation": 0.20, "test_performance": 0.25}
    score_without, _ = weighted_composite(comp_no_crdc, no_crdc_weights)
    tier_without, _ = assign_tiers(score_without)

    sub = has_crdc
    both_tiered = sub & tier_with.notna() & tier_without.notna()
    n_changed = int((tier_with[both_tiered] != tier_without[both_tiered]).sum())
    pct_changed = 100 * n_changed / both_tiered.sum() if both_tiered.sum() else np.nan
    rank_corr = (score_with[both_tiered].corr(score_without[both_tiered], method="spearman")
                 if both_tiered.sum() > 1 else np.nan)
    return {
        "n_schools_with_crdc_data": int(sub.sum()),
        "n_compared": int(both_tiered.sum()),
        "spearman_rank_corr": round(rank_corr, 4) if pd.notna(rank_corr) else np.nan,
        "n_schools_changed_tier": n_changed,
        "pct_schools_changed_tier": round(pct_changed, 1) if pd.notna(pct_changed) else np.nan,
    }


def poverty_funding_correlation(df, tier_num):
    """Report's explicit ask: correlation between poverty/funding overlay and the rigor score
    itself, reported directly rather than treated as an independent enrichment layer -- this is
    the number that would show whether the tier reproduces socioeconomic ordering."""
    out = {}
    for col in ["child_poverty_saipe", "per_resident_child_funding_state_local", "per_pupil_state_local"]:
        both = tier_num.notna() & df[col].notna()
        out[col] = round(tier_num[both].astype(float).corr(df.loc[both, col], method="spearman"), 4) if both.sum() > 1 else np.nan
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="modeling_dataset_v4_2026-07-24.csv")
    parser.add_argument("--version", default="v1")
    parser.add_argument("--spec", default=DEFAULT_SPEC, choices=sorted(COMPONENT_SPECS),
                        help="Component specification (v4 = qualifying density + verified IB)")
    parser.add_argument("--outdir", default=".")
    args = parser.parse_args()

    df = pd.read_csv(args.path, low_memory=False)
    print(f"Loaded {args.path}: {len(df):,} rows")

    components = COMPONENT_SPECS[args.spec]
    missing = [c for cols in components.values() for c in cols if c not in df.columns]
    if missing:
        raise SystemExit(
            f"Spec '{args.spec}' needs columns absent from {args.path}: {missing}. "
            f"The v4 features are derived in build_modeling_dataset.py -- rebuild the "
            f"modeling dataset, or pass --spec v3."
        )
    print(f"Component spec: {args.spec}")
    comp = build_components(df, components)
    weights = WEIGHT_SCHEMES[DEFAULT_SCHEME]
    score, avail = weighted_composite(comp, weights)
    tier_label, tier_num = assign_tiers(score, method=DEFAULT_TIER_METHOD)

    # ib_flag_candidate is never actually NaN (it's a boolean flag, always 0 or 1), so it would
    # otherwise show as "available" for every row despite carrying weight 0 in the default
    # scheme and contributing nothing to the score -- exclude zero-weight components from the
    # coverage/log stats below so "components used" reflects real signal, not a trivial always-
    # present flag.
    active = [n for n, w in weights.items() if w > 0]
    feature_log = avail.apply(lambda r: "+".join(n for n in active if r[n]) or "none", axis=1)
    n_components_used = avail[active].sum(axis=1)

    print("\n" + "=" * 72)
    print(f"RIGOR CLASSIFICATION -- weighting scheme: '{DEFAULT_SCHEME}' {weights}")
    print("=" * 72)

    scored = tier_num.notna().sum()
    print(f"\n[coverage] {scored:,}/{len(df):,} schools scored (have >=1 of {len(active)} active-weight components)")
    print(f"[coverage] component availability (ib shown for reference, weight 0 in default scheme): "
          + ", ".join(f"{c}={avail[c].mean()*100:.1f}%" for c in weights))
    print(f"[coverage] n_components_used distribution (active-weight components only):\n{n_components_used.value_counts().sort_index().to_string()}")

    # Tier-cut sensitivity: natural breaks (primary, per Wk5 "not equal buckets") vs. quantiles.
    q_label, q_num = assign_tiers(score, method="quantile")
    both_t = tier_num.notna() & q_num.notna()
    pct_same = 100 * (tier_num[both_t] == q_num[both_t]).mean() if both_t.sum() else float("nan")
    print(f"\n[tier distribution -- method='{DEFAULT_TIER_METHOD}' (Jenks natural breaks; "
          f"tier sizes vary, per Wk5 client note that rigor is NOT equal buckets)]")
    print(tier_label.value_counts().reindex(TIER_LABELS).to_string())
    print(f"\n[tier-cut sensitivity] natural-breaks vs. quantile: {pct_same:.1f}% of scored schools "
          f"land in the same tier; quantile sizes (for reference) = "
          f"{dict(q_label.value_counts().reindex(TIER_LABELS))}")

    full_coverage = avail[[n for n, w in weights.items() if w > 0]].all(axis=1)
    eff, total_var, n_full = effective_weights(comp, weights, full_coverage)
    print(f"\n[nominal vs effective weights] (full-coverage subset n={n_full:,}, composite variance={total_var:.4f})")
    for name, w in weights.items():
        if w > 0:
            print(f"   {name:20} nominal={w:.3f}  effective={eff.get(name, float('nan')):.3f}")

    print("\n[sensitivity analysis -- alternate weighting schemes vs. '{}']".format(DEFAULT_SCHEME))
    sens = sensitivity_analysis(comp, DEFAULT_SCHEME)
    print(sens.to_string(index=False))

    print("\n[CRDC-available vs. CRDC-unavailable scenario]")
    crdc_scenario = crdc_availability_scenario(comp, df)
    for k, v in crdc_scenario.items():
        print(f"   {k}: {v}")

    print("\n[poverty / funding correlation with rigor tier -- reported explicitly, not as enrichment]")
    pf_corr = poverty_funding_correlation(df, tier_num)
    for k, v in pf_corr.items():
        print(f"   spearman(tier, {k}) = {v}")

    out = df.copy()
    out["rigor_score"] = score
    out["rigor_tier_num"] = tier_num
    out["rigor_tier_label"] = tier_label
    out["rigor_n_components_used"] = n_components_used
    out["rigor_components_available"] = feature_log
    out["rigor_weighting_scheme"] = DEFAULT_SCHEME
    out["rigor_component_spec"] = args.spec
    out["rigor_tier_method"] = DEFAULT_TIER_METHOD
    out["rigor_tier_num_quantile"] = q_num          # alternate cut kept for downstream comparison
    out["rigor_tier_label_quantile"] = q_label

    date_tag = dt.date.today().isoformat()
    out_path = os.path.join(args.outdir, f"rigor_classification_{args.version}_{date_tag}.csv")
    out.to_csv(out_path, index=False)
    print(f"\nWrote {out_path} ({out.shape[0]:,} rows x {out.shape[1]} cols)")

    sens_path = os.path.join(args.outdir, f"rigor_sensitivity_{args.version}_{date_tag}.csv")
    sens.to_csv(sens_path, index=False)
    print(f"Wrote {sens_path}")
