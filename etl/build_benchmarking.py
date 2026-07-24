"""
build_benchmarking.py -- SAT/ACT performance benchmarking (report Section 4.5).

"SAT and ACT scores, where available at the school level, will be compared across schools and
used to enable peer-group comparisons by region, funding tier, and rigor classification ...
this benchmarking will be presented descriptively rather than as a validated predictor of
school quality ... the SEDA finding that achievement levels reproduce socioeconomic ordering
(Section 2.4) is treated as a reason for caution here as well, not only for the rigor tier."

This is deliberately a descriptive percentile-rank tool, not a model: for each school, report
where its SAT score sits relative to its region peers, its funding-tier peers, and its rigor-tier
peers -- three separate comparisons, not a combined prediction.

Data note: ACT scores in this pipeline (isbe_act_clean) are Illinois-only and cover 1.2% of
schools nationally -- too sparse to benchmark on at national scale. This first pass benchmarks
SAT only (sat_score_nu); ACT is left for a future IL-specific pass. sat_score_nu itself is
NU's average FRESHMAN SAT among the subset of students reporting it to NU at time of college
search -- selection-biased toward college-going, NU-engaged families, not a random sample of
each school's student body (flagged repeatedly elsewhere in this pipeline; carried forward
here rather than presented as if it were a clean measure).

Run:  python build_benchmarking.py rigor_classification_v3_2026-07-24.csv
"""
import argparse
import datetime as dt
import os

import numpy as np
import pandas as pd

SCORE_COL = "sat_score_nu"
FUNDING_COL = "per_resident_child_funding_state_local"
N_FUNDING_TIERS = 4  # quartiles


def assign_funding_tier(df):
    valid = df[FUNDING_COL].dropna()
    if valid.empty:
        return pd.Series(pd.NA, index=df.index, dtype="object")
    labels = [f"Q{i+1} ({'lowest' if i==0 else 'highest' if i==N_FUNDING_TIERS-1 else 'mid'} funding)"
              for i in range(N_FUNDING_TIERS)]
    tiers = pd.qcut(df[FUNDING_COL], N_FUNDING_TIERS, labels=labels, duplicates="drop")
    return tiers


def peer_percentile(df, group_col, score_col=SCORE_COL):
    """Each school's percentile rank of its SAT score within its own peer group (region,
    funding tier, or rigor tier) -- computed only among schools that have both the score and
    a valid group membership, groups smaller than 5 schools excluded (too small to benchmark
    against meaningfully, reported rather than silently included)."""
    valid = df[[group_col, score_col]].dropna()
    group_sizes = valid.groupby(group_col, observed=True)[score_col].transform("count")
    valid = valid[group_sizes >= 5]
    pct = valid.groupby(group_col, observed=True)[score_col].rank(pct=True) * 100
    return pct.reindex(df.index)


def group_summary(df, group_col, score_col=SCORE_COL):
    g = df.dropna(subset=[group_col, score_col]).groupby(group_col, observed=True)[score_col]
    summary = g.agg(["count", "mean", "std", "min", "max"]).round(1)
    return summary.sort_values("mean", ascending=False)


def ses_reproduction_check(df, tier_col, score_col=SCORE_COL):
    """Section 4.5's explicit caution, mirrored from the rigor-tier and clustering write-ups:
    report the correlation between SAT performance and poverty/funding directly, since the
    SEDA literature (Section 2.4) found achievement measures reproduce socioeconomic
    ordering -- this is the number that would show that, not something to infer indirectly."""
    out = {}
    for col in ["child_poverty_saipe", FUNDING_COL, "per_pupil_state_local"]:
        both = df[score_col].notna() & df[col].notna()
        out[col] = round(df.loc[both, score_col].corr(df.loc[both, col], method="spearman"), 4) if both.sum() > 1 else np.nan
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="rigor_classification_v3_2026-07-24.csv")
    parser.add_argument("--version", default="v3")
    parser.add_argument("--outdir", default=".")
    args = parser.parse_args()

    df = pd.read_csv(args.path, low_memory=False)
    print(f"Loaded {args.path}: {len(df):,} rows")
    print(f"\n[coverage] {SCORE_COL}: {100*df[SCORE_COL].notna().mean():.1f}% "
          f"({df[SCORE_COL].notna().sum():,} schools) -- ACT scores not benchmarked, "
          f"1.2% national coverage (IL-only), too sparse (see module docstring)")

    df["funding_tier"] = assign_funding_tier(df)

    print("\n" + "=" * 72)
    print("SECTION 4.5 -- PERFORMANCE BENCHMARKING (descriptive, not predictive)")
    print("=" * 72)

    for group_col, label in [("us_region", "region"), ("funding_tier", "funding tier"),
                              ("rigor_tier_label", "rigor tier")]:
        print(f"\n[{label}] SAT (sat_score_nu) by {group_col}:")
        print(group_summary(df, group_col).to_string())
        df[f"sat_percentile_by_{group_col}"] = peer_percentile(df, group_col)

    print("\n[SES-reproduction check -- same caution as the rigor tier and clustering, "
          "per Section 4.5's explicit instruction]")
    ses = ses_reproduction_check(df, "rigor_tier_label")
    for k, v in ses.items():
        print(f"   spearman(sat_score_nu, {k}) = {v}")

    print("\n[cross-tab] mean SAT by region x funding tier (small cells may be noisy):")
    cross = df.dropna(subset=["us_region", "funding_tier", SCORE_COL]).pivot_table(
        index="us_region", columns="funding_tier", values=SCORE_COL, aggfunc="mean", observed=True)
    print(cross.round(0).to_string())

    date_tag = dt.date.today().isoformat()
    out_path = os.path.join(args.outdir, f"benchmarking_{args.version}_{date_tag}.csv")
    df.to_csv(out_path, index=False)
    print(f"\nWrote {out_path} ({df.shape[0]:,} rows x {df.shape[1]} cols)")
