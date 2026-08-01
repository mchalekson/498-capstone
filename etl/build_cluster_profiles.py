"""
build_cluster_profiles.py -- interpretable profiles for the k-means clusters (report Section 4.3).

build_clustering.py assigns each complete-case school a cluster id, but a bare id ("cluster 6")
says nothing about what the group *is*. This summarizes each cluster so the pattern is legible:
size, its rigor-tier mix, and how it deviates from the clustered population on the location /
academic / funding / poverty features the clustering was built on. Deviations are z-relative
(cluster mean minus population mean, over population sd) so "+" = higher than a typical clustered
school and "-" = lower, comparably across features on different scales.

A short auto-label names each cluster from its two strongest deviations -- a hint for the deck,
not a claim; the numbers under it are the actual profile.

Run:  python build_cluster_profiles.py clustering_v4_2026-08-01.csv --version v4 --outdir ../csv_exports
"""
import argparse
import datetime as dt
import os

import numpy as np
import pandas as pd

# Features to profile (label -> column). Chosen to span the four axes the clustering uses.
PROFILE_FEATURES = {
    "rigor_score": "rigor_score",
    "ap_take_rate": "ap_take_rate",
    "ap_qualifying_density": "ap_qualifying_density",
    "dual_enrollment_rate": "dual_enrollment_rate",
    "testtaker_rate": "testtaker_rate",
    "grad_rate": "grad_rate_2021",
    "per_pupil_funding": "per_resident_child_funding_state_local",
    "child_poverty": "child_poverty_saipe",
    "socio_need": "socio_need_index",
}
NICE = {
    "rigor_score": "rigor", "ap_take_rate": "AP take-rate",
    "ap_qualifying_density": "AP density", "dual_enrollment_rate": "dual-enrollment",
    "testtaker_rate": "testtaker rate", "grad_rate": "grad rate",
    "per_pupil_funding": "funding", "child_poverty": "poverty", "socio_need": "socio-need",
}


def build_profiles(df, cluster_col="cluster_kmeans"):
    clustered = df[df[cluster_col].notna()].copy()
    clustered[cluster_col] = clustered[cluster_col].astype(int)

    feats = {lab: col for lab, col in PROFILE_FEATURES.items() if col in clustered.columns}
    pop_mean = {lab: pd.to_numeric(clustered[col], errors="coerce").mean() for lab, col in feats.items()}
    pop_sd = {lab: pd.to_numeric(clustered[col], errors="coerce").std() for lab, col in feats.items()}

    rows = []
    for cid, g in clustered.groupby(cluster_col):
        row = {"cluster": cid, "size": len(g)}
        # rigor tier mix (share in the top two tiers, a quick "how demanding is this group")
        tiers = g["rigor_tier_label"].value_counts(normalize=True)
        row["pct_demanding_plus"] = round(100 * tiers.reindex(
            ["Demanding", "Very Demanding", "Most Demanding"]).fillna(0).sum(), 1)
        # top region
        if "us_region" in g:
            reg = g["us_region"].mode()
            row["top_region"] = reg.iloc[0] if len(reg) else ""
        # z-relative deviations
        devs = {}
        for lab, col in feats.items():
            m = pd.to_numeric(g[col], errors="coerce").mean()
            devs[lab] = (m - pop_mean[lab]) / pop_sd[lab] if pop_sd[lab] else np.nan
            row[f"z_{lab}"] = round(devs[lab], 2) if pd.notna(devs[lab]) else np.nan
        # auto-label from the two largest-magnitude deviations
        ranked = sorted((l for l in devs if pd.notna(devs[l])), key=lambda l: -abs(devs[l]))[:2]
        parts = [f"{'high' if devs[l] > 0 else 'low'} {NICE[l]}" for l in ranked]
        row["auto_label"] = ", ".join(parts)
        rows.append(row)

    prof = pd.DataFrame(rows).sort_values("cluster").reset_index(drop=True)
    # order columns readably
    front = ["cluster", "size", "auto_label", "pct_demanding_plus", "top_region"]
    zcols = [c for c in prof.columns if c.startswith("z_")]
    return prof[[c for c in front if c in prof.columns] + zcols]


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("path")
    p.add_argument("--version", default="v4")
    p.add_argument("--outdir", default=".")
    args = p.parse_args()

    df = pd.read_csv(args.path, low_memory=False)
    prof = build_profiles(df)
    print(prof.to_string(index=False))

    date_tag = dt.date.today().isoformat()
    out = os.path.join(args.outdir, f"cluster_profiles_{args.version}_{date_tag}.csv")
    prof.to_csv(out, index=False)
    print(f"\nWrote {out} ({len(prof)} clusters x {prof.shape[1]} cols)")
