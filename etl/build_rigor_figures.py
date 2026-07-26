"""
build_rigor_figures.py
----------------------
Deck-ready figures for the Section 4.1 rigor classification, built directly from
the team's shipped pipeline outputs (does NOT recompute the index):

  benchmarking_v3_*.csv          -> mean SAT by rigor tier (independent validation)
  rigor_classification_v4_*.csv  -> tier~poverty (SES-robustness annotation)
  rigor_analysis_v3_*.csv        -> AP-efficiency quadrant + "tier hides them"

All headline numbers were independently re-derived from these CSVs and match the
team docs (BENCHMARKING.md, RIGOR_ANALYSIS.md): SAT 1052->1303 monotonic,
selective&effective n=1597 with only 9 in the top tier.

Figures:
  rigor_validation.png     mean SAT rises across tiers on a measure not used to build them
  ap_efficiency.png        offering-breadth x AP-score quadrant + tier placement of the
                           "selective & effective" schools the additive tier hides
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import spearmanr

NAVY, PURPLE, GREEN, GREY, ORANGE = "#4E2A84", "#836EAA", "#2E7D32", "#B6ACD1", "#E4A011"
TIERS = ["Below Average", "Average", "Demanding", "Very Demanding", "Most Demanding"]

bench = pd.read_csv("benchmarking_v3_2026-07-24.csv", low_memory=False)
rig   = pd.read_csv("rigor_classification_v4_2026-07-24.csv", low_memory=False)
anal  = pd.read_csv("rigor_analysis_v3_2026-07-24.csv", low_memory=False)


def sp(a, b, d):
    d2 = d.dropna(subset=[a, b])
    return spearmanr(d2[a], d2[b]).correlation


# ---------------------------------------------------------------------------
# Figure 1 — rigor tier validated against independent SAT + SES robustness
# ---------------------------------------------------------------------------
def fig_validation(out):
    b = bench.dropna(subset=["sat_score_nu", "rigor_tier_label"])
    g = b.groupby("rigor_tier_label")["sat_score_nu"].agg(["mean", "count"]).reindex(TIERS)

    tier_pov = sp("rigor_tier_num", "child_poverty_saipe", rig)
    sat_pov  = sp("sat_score_nu",   "child_poverty_saipe", bench)

    fig, ax = plt.subplots(figsize=(9.5, 5.8))
    x = np.arange(len(TIERS))
    bars = ax.bar(x, g["mean"], color=[GREY, PURPLE, NAVY, NAVY, "#2E1150"], width=0.66)
    for i, (m, n) in enumerate(zip(g["mean"], g["count"])):
        ax.text(i, m + 5, f"{m:.0f}", ha="center", fontweight="bold", color="#222", fontsize=11)
        ax.text(i, 40, f"n={int(n):,}", ha="center", color="white", fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels(TIERS, fontsize=10)
    ax.set_ylabel("Mean SAT (NU-reported)")
    ax.set_ylim(1000, 1340)
    ax.set_title("The rigor tier validates against data it was not built from\n"
                 f"Mean SAT climbs {g['mean'].iloc[0]:.0f} → {g['mean'].iloc[-1]:.0f} "
                 "across tiers, no inversions",
                 fontsize=12.5, loc="left")

    # SES-robustness annotation box
    txt = (f"SES robustness (Spearman vs. child poverty):\n"
           f"  rigor tier ~ poverty  =  {tier_pov:+.2f}\n"
           f"  raw SAT ~ poverty      =  {sat_pov:+.2f}\n"
           f"→ the tier is ~{abs(sat_pov/tier_pov):.1f}× LESS SES-confounded\n"
           f"   than the outcome it tracks")
    ax.text(0.02, 0.97, txt, transform=ax.transAxes, va="top", fontsize=9.3,
            bbox=dict(boxstyle="round,pad=0.5", fc="#F3F0F8", ec=NAVY, lw=1))
    ax.text(0.02, -0.16,
            "Caveat: SAT is NU-reported freshman SAT (college-going, NU-engaged families) — "
            "a validation signal, not a representative sample.",
            transform=ax.transAxes, fontsize=8, color="#666")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 2 — AP efficiency (Bob's "low offering / high scores")
# ---------------------------------------------------------------------------
def fig_efficiency(out):
    d = anal.dropna(subset=["ap_tests_offered", "ap_score_nu"]).copy()
    med_off = d["ap_tests_offered"].median()
    med_sc  = d["ap_score_nu"].median()
    se_mask = d["ap_efficiency_quadrant"].str.startswith("Selective", na=False)

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 6), gridspec_kw={"width_ratios": [1.55, 1]})

    # -- left: quadrant scatter, selective&effective highlighted --
    ax = axes[0]
    ax.scatter(d.loc[~se_mask, "ap_tests_offered"], d.loc[~se_mask, "ap_score_nu"],
               s=6, alpha=0.18, color=GREY, edgecolors="none", label="Other schools")
    ax.scatter(d.loc[se_mask, "ap_tests_offered"], d.loc[se_mask, "ap_score_nu"],
               s=10, alpha=0.55, color=GREEN, edgecolors="none",
               label=f"Selective & effective (n={se_mask.sum():,})")
    ax.axvline(med_off, color="#999", lw=1, ls="--")
    ax.axhline(med_sc, color="#999", lw=1, ls="--")
    ax.text(med_off * 0.45, 4.6, "SELECTIVE & EFFECTIVE\nfew offered · high scores\n(Bob's case)",
            ha="center", color=GREEN, fontsize=9.5, fontweight="bold")
    ax.set_xlabel("AP courses offered (breadth)")
    ax.set_ylabel("Mean AP exam score (1–5)")
    ax.set_title("AP efficiency: schools that punch above their offering weight",
                 fontsize=12, loc="left")
    ax.legend(loc="lower right", frameon=False, markerscale=2, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)

    # -- right: where those schools land by tier (the "tier hides them" finding) --
    ax2 = axes[1]
    se_by_tier = anal.loc[anal["ap_efficiency_quadrant"].str.startswith("Selective", na=False),
                          "rigor_tier_label"].value_counts().reindex(TIERS).fillna(0)
    colors = [GREY, GREY, GREY, GREY, ORANGE]
    ax2.barh(range(len(TIERS)), se_by_tier.values, color=colors)
    for i, v in enumerate(se_by_tier.values):
        ax2.text(v + 8, i, f"{int(v):,}", va="center", fontsize=9.5)
    ax2.set_yticks(range(len(TIERS)))
    ax2.set_yticklabels(TIERS, fontsize=9.5)
    ax2.invert_yaxis()
    ax2.set_xlabel("Selective & effective schools")
    ax2.set_title("...but only 9 reach 'Most Demanding'\nthe additive tier hides them",
                  fontsize=11, loc="left")
    ax2.spines[["top", "right"]].set_visible(False)

    fig.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    fig_validation("rigor_validation.png")
    fig_efficiency("ap_efficiency.png")
    print("Wrote: rigor_validation.png, ap_efficiency.png")
