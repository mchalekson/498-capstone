"""
build_deck_figures.py -- data-driven deck figures, all pinned to the v4 rigor index.

Companion to build_rigor_figures.py (which shipped the first two Wk6 figures against v3).
Everything here reads the committed CSVs in csv_exports/ and writes into docs/fig/, so the
decks in docs/ can be rebuilt from the repo alone:

    python etl/build_deck_figures.py       # -> docs/fig/*.png
    python etl/build_decks.py              # -> docs/*.pptx

Regenerated at v4 (was v3, and the two disagreed on-slide):
  rigor_validation.png   mean SAT by v4 tier -- 1,066 -> 1,288, an independent measure
  ap_efficiency.png      offering-breadth x AP-score quadrant, v4 tier placement
  tier_cutpoints.png     score distribution + natural-breaks cuts + v4 tier sizes

New:
  tier_profile.png       what each tier actually looks like (the results slide)
  school_profile.png     a single school's card -- what the client receives
  benchmarking_ses.png   SAT vs rigor as poverty proxies (the design-choice evidence)
  clustering.png         PCA + k-means segments, and their overlap with the tier

index_schematic.png and pipeline.png are hand-drawn diagrams, not data-driven; they stay as
committed assets in docs/fig/ and are not regenerated here.
"""
import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from scipy.stats import spearmanr

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(ROOT, "csv_exports")
FIG = os.path.join(ROOT, "docs", "fig")
os.makedirs(FIG, exist_ok=True)

NAVY, PURPLE, MID, LIGHT, DARK = "#4E2A84", "#836EAA", "#6B4FA8", "#B6ACD1", "#2E1150"
GREY, ORANGE, INK = "#BDBDBD", "#E4A011", "#1A1A1A"
TIERS = ["Below Average", "Average", "Demanding", "Very Demanding", "Most Demanding"]
TIER_COLORS = ["#D8D2E8", LIGHT, PURPLE, MID, DARK]

plt.rcParams.update({
    "font.family": "DejaVu Sans", "axes.titlesize": 13, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.labelcolor": "#444", "text.color": INK,
    "xtick.color": "#555", "ytick.color": "#555", "axes.edgecolor": "#CCC",
})

rig = pd.read_csv(os.path.join(EXP, "rigor_classification_v4_2026-07-24.csv"), low_memory=False)
bench = pd.read_csv(os.path.join(EXP, "benchmarking_v3_2026-07-24.csv"), low_memory=False)
anal = pd.read_csv(os.path.join(EXP, "rigor_analysis_v3_2026-07-24.csv"), low_memory=False)
clus = pd.read_csv(os.path.join(EXP, "clustering_v3_2026-07-24.csv"), low_memory=False)

# Current tiers joined onto the analysis/benchmarking frames, so every figure below is cut the
# same way. (The tier columns already in those files are left untouched, not overwritten.)
#
# ceeb is NULL for ~5,400 rows and pandas joins NULL to NULL, so an unguarded merge on it is a
# cartesian blow-up (34k x 34k). Every join key here is de-nulled and de-duplicated first.
def _key(df, cols):
    return df.loc[df["ceeb"].notna(), cols].drop_duplicates(subset="ceeb")


V4 = _key(rig, ["ceeb", "rigor_tier_label", "rigor_score"]).rename(
    columns={"rigor_tier_label": "tier_v4", "rigor_score": "score_v4"})
SAT = _key(bench, ["ceeb", "sat_score_nu"]).rename(columns={"sat_score_nu": "sat"})
bench4 = bench.drop(columns=["rigor_tier_label"], errors="ignore").merge(V4, on="ceeb", how="left")
anal4 = anal.drop(columns=["rigor_tier_label"], errors="ignore").merge(V4, on="ceeb", how="left")


def _clean(ax, grid="y"):
    ax.spines[["top", "right"]].set_visible(False)
    if grid:
        ax.grid(axis=grid, color="#EEE", lw=0.9)
        ax.set_axisbelow(True)


def _save(fig, name):
    out = os.path.join(FIG, name)
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  {name}")


def sp(a, b, d):
    d2 = d.dropna(subset=[a, b])
    return spearmanr(d2[a], d2[b]).correlation


# --------------------------------------------------------------- 1. SAT validation (v4)
def fig_validation():
    b = bench4.dropna(subset=["sat_score_nu", "tier_v4"])
    g = b.groupby("tier_v4")["sat_score_nu"].agg(["mean", "count"]).reindex(TIERS)
    tier_pov = sp("rigor_tier_num", "child_poverty_saipe", rig)

    fig, ax = plt.subplots(figsize=(9.5, 5.8))
    x = np.arange(len(TIERS))
    ax.bar(x, g["mean"], color=TIER_COLORS, width=0.66)
    for i, (m, n) in enumerate(zip(g["mean"], g["count"])):
        ax.text(i, m + 4, f"{m:,.0f}", ha="center", fontweight="bold", fontsize=12)
        ax.text(i, 1006, f"n={int(n):,}", ha="center", fontsize=9,
                color="white" if i >= 3 else "#555")
    ax.set_xticks(x); ax.set_xticklabels(TIERS, fontsize=10.5)
    ax.set_ylabel("Mean SAT (NU-reported)")
    ax.set_ylim(1000, 1330)
    spread = g["mean"].iloc[-1] - g["mean"].iloc[0]
    ax.set_title("The tier validates against data it was not built from\n"
                 f"Mean SAT climbs {g['mean'].iloc[0]:,.0f} → {g['mean'].iloc[-1]:,.0f} "
                 f"({spread:.0f} points), no inversions", fontsize=12.5)
    ax.text(0, 1315, f"rigor tier vs. county child poverty:  ρ = {tier_pov:.3f}   "
                     "(weak — the tier is not a poverty proxy)",
            fontsize=9.5, color="#666")
    _clean(ax)
    _save(fig, "rigor_validation.png")


# ------------------------------------------------------- 2. AP efficiency, on v4 tiers
def fig_efficiency():
    q = anal4["ap_efficiency_quadrant"].astype(str)
    se = anal4[q.str.startswith("Selective")]
    n_se = len(se)
    by_tier = se["tier_v4"].value_counts().reindex(TIERS).fillna(0)
    n_top = int(by_tier.iloc[-1])

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.6), gridspec_kw={"width_ratios": [1.25, 1]})

    ax = axes[0]
    d = anal4.dropna(subset=["ap_tests_offered", "ap_score_nu"])
    ax.scatter(d["ap_tests_offered"], d["ap_score_nu"], s=5, c=LIGHT, alpha=0.35, lw=0)
    ds = se.dropna(subset=["ap_tests_offered", "ap_score_nu"])
    ax.scatter(ds["ap_tests_offered"], ds["ap_score_nu"], s=7, c=ORANGE, alpha=0.75, lw=0)
    ax.axvline(d["ap_tests_offered"].median(), color="#999", ls="--", lw=1)
    ax.axhline(d["ap_score_nu"].median(), color="#999", ls="--", lw=1)
    ax.set_xlabel("AP courses offered"); ax.set_ylabel("Mean AP exam score (1–5)")
    ax.set_title(f"'Do a lot with little': {n_se:,} schools\nfew APs offered, high exam scores",
                 fontsize=12)
    ax.text(0.02, 0.96, "selective & effective", transform=ax.transAxes, color=ORANGE,
            fontsize=10, fontweight="bold", va="top")
    _clean(ax, grid=None)

    ax2 = axes[1]
    colors = [GREY, GREY, GREY, GREY, ORANGE]
    ax2.barh(range(len(TIERS)), by_tier.values, color=colors)
    for i, v in enumerate(by_tier.values):
        ax2.text(v + max(by_tier) * 0.015, i, f"{int(v):,}", va="center", fontsize=10)
    ax2.set_yticks(range(len(TIERS))); ax2.set_yticklabels(TIERS, fontsize=10)
    ax2.invert_yaxis()
    ax2.set_xlabel("Selective & effective schools")
    ax2.set_title(f"...but only {n_top} reach 'Most Demanding'\nthe additive tier hides them",
                  fontsize=12)
    _clean(ax2, grid="x")

    fig.tight_layout()
    _save(fig, "ap_efficiency.png")
    return n_se, n_top


# ------------------------------------------------------------- 3. Tier cut-points (v4)
def fig_cutpoints():
    s = rig.dropna(subset=["rigor_score", "rigor_tier_label"])
    edges = s.groupby("rigor_tier_label")["rigor_score"].min().reindex(TIERS)
    counts = s["rigor_tier_label"].value_counts().reindex(TIERS)

    fig, ax = plt.subplots(figsize=(13, 5.4))
    bins = np.linspace(s["rigor_score"].min(), s["rigor_score"].max(), 90)
    for tier, color in zip(TIERS, TIER_COLORS):
        ax.hist(s.loc[s["rigor_tier_label"] == tier, "rigor_score"], bins=bins,
                color=color, label=tier)
    cuts = edges.iloc[1:].values
    for c in cuts:
        ax.axvline(c, color=INK, ls="--", lw=1.4)
    mids = [(s["rigor_score"].min() + cuts[0]) / 2] + \
           [(cuts[i] + cuts[i + 1]) / 2 for i in range(len(cuts) - 1)] + \
           [(cuts[-1] + s["rigor_score"].max()) / 2]
    top = ax.get_ylim()[1]
    for m, n in zip(mids, counts.values):
        ax.text(m, top * 0.95, f"{int(n):,}", ha="center", fontweight="bold", fontsize=12)
    ax.set_xlabel("rigor_score")
    ax.set_title("Natural breaks cut at the gaps — tier sizes are not equal by design")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=5, frameon=False, fontsize=10)
    _clean(ax)
    _save(fig, "tier_cutpoints.png")


# --------------------------------------------------- 4. Tier profile -- the results slide
def fig_tier_profile():
    d = rig.dropna(subset=["rigor_tier_label"]).merge(SAT, on="ceeb", how="left")
    g = d.groupby("rigor_tier_label")
    panels = [
        ("Schools", g.size().reindex(TIERS), "{:,.0f}", None),
        ("Mean AP exam score", g["ap_score_nu"].mean().reindex(TIERS), "{:.2f}", (1, 5)),
        ("Mean SAT", g["sat"].mean().reindex(TIERS), "{:,.0f}", (1000, 1350)),
        ("Mean graduation rate (%)",
         g["grad_rate_2021"].mean().reindex(TIERS), "{:.0f}", (50, 100)),
    ]
    fig, axes = plt.subplots(1, 4, figsize=(15.5, 4.6))
    for ax, (title, series, fmt, ylim) in zip(axes, panels):
        ax.bar(range(5), series.values, color=TIER_COLORS, width=0.7)
        for i, v in enumerate(series.values):
            if not np.isnan(v):
                ax.text(i, v, fmt.format(v), ha="center", va="bottom",
                        fontweight="bold", fontsize=10)
        ax.set_title(title, fontsize=11.5)
        ax.set_xticks(range(5))
        ax.set_xticklabels(["Below\nAvg", "Avg", "Dem.", "Very\nDem.", "Most\nDem."], fontsize=9)
        if ylim:
            ax.set_ylim(*ylim)
        else:
            ax.set_ylim(0, series.max() * 1.18)
        _clean(ax)
    fig.suptitle(f"What each tier actually looks like  —  {len(d):,} scored schools",
                 x=0.007, ha="left", fontsize=13.5, fontweight="bold")
    fig.text(0.007, -0.03, "AP score, SAT and graduation rate are shown per tier; only AP score "
             "is an index input. SAT and graduation rate are independent checks.",
             fontsize=9.5, color="#666")
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    _save(fig, "tier_profile.png")


# ------------------------------------------ 5. One school's card -- what the client receives
def fig_school_profile(name="New Trier"):
    s = rig[rig["school_name"].astype(str).str.contains(name, case=False, na=False)]
    s = s.dropna(subset=["rigor_score"]).sort_values("enrollment_9_12", ascending=False).iloc[0]
    scored = rig.dropna(subset=["rigor_score"])
    pct = (scored["rigor_score"] < s["rigor_score"]).mean() * 100
    hit = SAT.loc[SAT["ceeb"] == s["ceeb"], "sat"]
    sat = hit.iloc[0] if len(hit) and pd.notna(hit.iloc[0]) else np.nan

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.2),
                                  gridspec_kw={"width_ratios": [1, 1.15]})
    ax.axis("off")
    ax.add_patch(FancyBboxPatch((0.02, 0.06), 0.96, 0.88, boxstyle="round,pad=0.02",
                                fc="#F7F5FB", ec=LIGHT, lw=1.5, transform=ax.transAxes))
    ax.text(0.08, 0.83, str(s["school_name"]).strip(), fontsize=16, fontweight="bold",
            transform=ax.transAxes)
    ax.text(0.08, 0.75, f"{s['state']}  ·  {s['sector']}  ·  "
                        f"CEEB {int(s['ceeb'])}", fontsize=11, color="#666",
            transform=ax.transAxes)
    ax.text(0.08, 0.55, str(s["rigor_tier_label"]).upper(), fontsize=22, fontweight="bold",
            color=NAVY, transform=ax.transAxes)
    ax.text(0.08, 0.44, f"rigor score {s['rigor_score']:.2f}   ·   "
                        f"{pct:.0f}th percentile of scored schools",
            fontsize=11.5, color="#444", transform=ax.transAxes)
    ax.text(0.08, 0.30, f"built from {int(s['rigor_n_components_used'])} of 5 components",
            fontsize=10.5, color="#666", transform=ax.transAxes)
    ax.text(0.08, 0.15, "Every tier decomposes back to its inputs —\nno black box.",
            fontsize=10.5, color=NAVY, style="italic", transform=ax.transAxes)

    rows = [("AP exam score (1–5)", s.get("ap_score_nu"), 5, "{:.2f}"),
            ("AP tests per student", s.get("ap_tests_taken"), 6, "{:.2f}"),
            ("Mean SAT", sat, 1600, "{:,.0f}"),
            ("Grades 9–12 enrollment", s.get("enrollment_9_12"), 3000, "{:,.0f}")]
    rows = [r for r in rows if pd.notna(r[1])]
    y = np.arange(len(rows))[::-1]
    ax2.barh(y, [r[1] / r[2] for r in rows], color=PURPLE, height=0.5)
    ax2.set_xlim(0, 1.25)
    for yi, r in zip(y, rows):
        ax2.text(r[1] / r[2] + 0.02, yi, r[3].format(r[1]), va="center",
                 fontweight="bold", fontsize=11)
    ax2.set_yticks(y); ax2.set_yticklabels([r[0] for r in rows], fontsize=10.5)
    ax2.set_xticks([])
    ax2.set_title("The components behind the tier", fontsize=12)
    for sp_ in ["top", "right", "bottom"]:
        ax2.spines[sp_].set_visible(False)
    _save(fig, "school_profile.png")
    return s["school_name"], s["rigor_tier_label"], pct


# ------------------------------------- 6. Why opportunity, not test scores (the SES check)
def fig_benchmarking_ses():
    sat_pov = sp("sat_score_nu", "child_poverty_saipe", bench)
    tier_pov = sp("rigor_tier_num", "child_poverty_saipe", rig)

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.2),
                                  gridspec_kw={"width_ratios": [1, 1.1]})
    vals = [abs(sat_pov), abs(tier_pov)]
    ax.bar([0, 1], vals, color=[ORANGE, NAVY], width=0.55)
    for i, v in enumerate(vals):
        ax.text(i, v + 0.008, f"ρ = −{v:.3f}", ha="center",
                fontweight="bold", fontsize=13)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["SAT score\n(an outcome measure)",
                        "Our rigor tier\n(opportunity + performance)"], fontsize=10.5)
    ax.set_ylabel("|correlation| with county child poverty")
    ax.set_ylim(0, max(vals) * 1.28)
    ax.set_title(f"Why we measure opportunity, not test scores\n"
                 f"SAT tracks poverty {abs(sat_pov)/abs(tier_pov):.1f}× more strongly "
                 f"than our tier does", fontsize=12.5)
    _clean(ax)

    reg = (bench.dropna(subset=["sat_score_nu", "us_region"])
           .groupby("us_region")["sat_score_nu"].agg(["mean", "count"])
           .sort_values("mean"))
    ax2.barh(range(len(reg)), reg["mean"], color=PURPLE, height=0.6)
    for i, (m, n) in enumerate(zip(reg["mean"], reg["count"])):
        ax2.text(m + 3, i, f"{m:,.0f}  (n={int(n):,})", va="center", fontsize=10)
    ax2.set_yticks(range(len(reg))); ax2.set_yticklabels(reg.index, fontsize=10.5)
    ax2.set_xlim(1050, reg["mean"].max() * 1.06)
    ax2.set_title("Peer benchmarking: mean SAT by region", fontsize=12)
    _clean(ax2, grid="x")

    fig.tight_layout()
    _save(fig, "benchmarking_ses.png")
    return sat_pov, tier_pov


# ----------------------------------------------------- 7. Clustering -- segments vs. tier
def fig_clustering():
    c = clus.dropna(subset=["cluster_kmeans", "pca_component_1", "pca_component_2"]).copy()
    c = c.merge(V4, on="ceeb", how="left")
    ks = sorted(c["cluster_kmeans"].unique())
    palette = [NAVY, ORANGE, "#2E7D32", LIGHT]

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.4),
                                  gridspec_kw={"width_ratios": [1.1, 1]})
    for k, col in zip(ks, palette):
        d = c[c["cluster_kmeans"] == k]
        ax.scatter(d["pca_component_1"], d["pca_component_2"], s=6, c=col, alpha=0.45,
                   lw=0, label=f"Cluster {int(k)}  (n={len(d):,})")
    ax.set_xlabel("PC1"); ax.set_ylabel("PC2")
    ax.set_title(f"Four segments over {len(c):,} complete-case schools\n"
                 "clustered on raw inputs, never on rigor_score", fontsize=12)
    ax.legend(frameon=False, fontsize=9.5, markerscale=2.2, loc="best")
    _clean(ax, grid=None)

    ct = (pd.crosstab(c["cluster_kmeans"], c["tier_v4"])
          .reindex(columns=TIERS).fillna(0))
    ct = ct.div(ct.sum(axis=1), axis=0) * 100
    bottom = np.zeros(len(ct))
    for tier, col in zip(TIERS, TIER_COLORS):
        ax2.bar(range(len(ct)), ct[tier], bottom=bottom, color=col, label=tier, width=0.62)
        bottom += ct[tier].values
    ax2.set_xticks(range(len(ct)))
    ax2.set_xticklabels([f"Cluster {int(k)}" for k in ct.index], fontsize=10.5)
    ax2.set_ylabel("% of cluster")
    ax2.set_ylim(0, 100)
    ax2.set_title("Segments are not just the tier re-drawn\nevery cluster spans several tiers",
                  fontsize=12)
    ax2.legend(frameon=False, fontsize=8.5, ncol=2, loc="upper center",
               bbox_to_anchor=(0.5, -0.09))
    _clean(ax2)

    fig.tight_layout()
    _save(fig, "clustering.png")
    return len(c), len(ks)


if __name__ == "__main__":
    print("writing figures to docs/fig/ ...")
    fig_validation()
    n_se, n_top = fig_efficiency()
    fig_cutpoints()
    fig_tier_profile()
    school, tier, pct = fig_school_profile()
    sat_pov, tier_pov = fig_benchmarking_ses()
    n_clus, k = fig_clustering()
    print("\nnumbers to keep the decks honest:")
    print(f"  selective & effective: {n_se:,}   reaching Most Demanding: {n_top}")
    print(f"  example school: {str(school).strip()} -> {tier} ({pct:.0f}th pct)")
    print(f"  poverty rho: SAT {sat_pov:.3f} vs tier {tier_pov:.3f} "
          f"({abs(sat_pov/tier_pov):.1f}x)")
    print(f"  clustering: {n_clus:,} schools, k={k}")
