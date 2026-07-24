"""
build_coverage_report.py -- feature coverage split by sector (public vs private).

Answers the Week-5 client question directly: "AP/SAT participation was ~30%, now it's ~80% --
and for private schools it's __%?" Coverage is not missing-at-random here (CRDC is public-only
by federal design; NU analytics track NU's recruiting universe), so reporting a single overall
number hides the structural public/private gap the client asked about. This produces the
per-sector breakdown instead, and is the same kind of merge-transparency reporting Bob asked
for on every join.

Run:  python build_coverage_report.py modeling_dataset_v3_2026-07-24.csv --version v3
Produces: coverage_by_sector_<version>.csv  (+ prints a readable table)
"""
import argparse
import os

import pandas as pd

# (column, human label) -- the features the Wk5 meeting named, grouped for readability
FEATURE_GROUPS = {
    "AP -- opportunity": [
        # ap_offered omitted: it's an always-populated 0/1 flag, so notna-coverage is a
        # meaningless 100% -- the informative AP-coverage signals are the counts/rates below.
        ("number_of_ap_classes_offered_mid", "# AP classes offered (NU)"),
        ("ap_tests_taken", "AP tests taken / student (NU)"),
        ("ap_take_rate", "AP take-rate (taken/offered)"),
        ("ap_participation", "AP participation (CRDC)"),
    ],
    "AP -- performance": [
        ("ap_score_nu", "AP exam score 1-5 (NU)"),
    ],
    "Standardized testing": [
        ("sat_participation_nu", "SAT participation (NU)"),
        ("testtaker_rate", "SAT/ACT testtaker rate (CRDC)"),
        ("sat_score_nu", "Avg SAT score (NU)"),
        ("act_composite_il", "ACT composite (ISBE, IL only)"),
    ],
    "Other academic / context": [
        ("dual_enrollment_rate", "Dual enrollment (CRDC)"),
        ("ib_flag_v2", "IB flag (CRDC+adjudicated)"),
        ("grad_rate_2021", "Graduation rate (EDFacts)"),
        ("frl_rate", "Free/reduced lunch rate"),
        ("socio_need_index", "Neighborhood context (NU)"),
        ("per_resident_child_funding_state_local", "Funding proxy (F-33/SAIPE)"),
        ("child_poverty_saipe", "County child poverty (SAIPE)"),
    ],
}


def coverage_by_sector(df):
    rows = []
    sectors = ["public", "private"]
    n_by_sector = {s: int((df["sector"] == s).sum()) for s in sectors}
    for group, feats in FEATURE_GROUPS.items():
        for col, label in feats:
            if col not in df.columns:
                continue
            rec = {"group": group, "feature": label, "column": col}
            for s in sectors:
                sub = df[df["sector"] == s]
                rec[f"{s}_pct"] = round(100 * sub[col].notna().mean(), 1) if len(sub) else float("nan")
                rec[f"{s}_n"] = int(sub[col].notna().sum())
            rec["overall_pct"] = round(100 * df[col].notna().mean(), 1)
            rows.append(rec)
    return pd.DataFrame(rows), n_by_sector


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="modeling_dataset_v3_2026-07-24.csv")
    parser.add_argument("--version", default="v3")
    parser.add_argument("--outdir", default=".")
    args = parser.parse_args()

    df = pd.read_csv(args.path, low_memory=False)
    cov, n_by_sector = coverage_by_sector(df)

    print("=" * 78)
    print("FEATURE COVERAGE BY SECTOR (public vs private) -- Wk5 client question")
    print("=" * 78)
    print(f"Universe: {len(df):,} high schools "
          f"(public={n_by_sector['public']:,}, private={n_by_sector['private']:,})\n")
    show = cov[["feature", "public_pct", "private_pct", "overall_pct"]].copy()
    show.columns = ["feature", "public %", "private %", "overall %"]
    print(show.to_string(index=False))
    print("\nNote: coverage is NOT missing-at-random. CRDC (AP participation, dual enrollment, "
          "\ntesttaker rate) is public-school-only by federal design -> ~0% private. NU analytics "
          "\n(AP/SAT scores) track NU's recruiting universe. Read low private coverage as a "
          "\nstructural data gap, not random missingness.")

    out_path = os.path.join(args.outdir, f"coverage_by_sector_{args.version}.csv")
    cov.to_csv(out_path, index=False)
    print(f"\nWrote {out_path} ({len(cov)} features)")
