"""
build_rigor_figures.py
----------------------
Deck-ready figures for the Section 4.1 rigor classification, built directly from
the team's shipped pipeline outputs. Everything reads the **v4** chain so no two
figures disagree with each other.

Text discipline: a title and the graph. Nothing else. The title states what is
plotted -- it is a label, not a sentence and not a conclusion. No subtitles, no
source lines, no annotation boxes, no callouts. Numbers on the marks are the data.
Interpretation is said out loud or read in docs/.

Inputs (all in csv_exports/):
  modeling_dataset_v4_*.csv, rigor_classification_v4_*.csv, rigor_sensitivity_v4_*.csv,
  benchmarking_v4_*.csv, rigor_analysis_v4_*.csv, coverage_by_sector_v3.csv,
  predictive_validation_metrics_v4_*.csv, predictive_validation_importance_v4_*.csv

Figures:
  match_rates.png          the three defensible match rates
  coverage_by_sector.png   feature coverage, public vs private
  ap_efficiency.png        offering breadth x AP score, and where those schools land
  weights.png              nominal vs effective weights + weighting sensitivity
  tier_cutpoints.png       score distribution with the Jenks cuts
  rigor_validation.png     mean SAT across tiers, a measure not used to build them
  pipeline.png             sources -> crosswalk -> freeze -> index -> analysis
  index_schematic.png      how a score is computed
  predictive_validation.png  does opportunity structure beat SES alone

Run from csv_exports/:  PYTHONPATH=../etl python3 ../etl/build_rigor_figures.py
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

import build_rigor_classification as rc

# --- palette -----------------------------------------------------------------
# Categorical slots validated with the dataviz skill's checker (light surface):
# lightness band, chroma floor, CVD separation, normal-vision floor, contrast all PASS.
VIOLET = "#4a3aa7"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
TIER_RAMP = ["#dcd8f2", "#b3a9e2", "#8878cd", "#5f4cb8", "#372a80"]
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#8d8b85", "#e6e4de"
SHELL = "#efedf5"

TIERS = ["Below Average", "Average", "Demanding", "Very Demanding", "Most Demanding"]

MODELING = "modeling_dataset_v4_2026-08-01.csv"
RIGOR = "rigor_classification_v4_2026-08-01.csv"
SENS = "rigor_sensitivity_v4_2026-08-01.csv"
BENCH = "benchmarking_v4_2026-08-01.csv"
ANALYSIS = "rigor_analysis_v4_2026-08-01.csv"
COVERAGE = "coverage_by_sector_v4.csv"
PV_METRICS = "predictive_validation_metrics_v4_2026-08-01.csv"
PV_IMPORTANCE = "predictive_validation_importance_v4_2026-08-01.csv"


def _style(ax, grid_axis="y"):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9.5, length=0)
    ax.set_axisbelow(True)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID, lw=0.8)


def _title(ax, headline, size=13):
    """Headline only. No subtitle, no annotation, no source line -- the chart
    speaks for itself and everything else is said out loud or read in docs/."""
    ax.set_title(headline, fontsize=size, loc="left", color=INK, pad=10,
                 fontweight="semibold")


def _save(fig, out):
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------------------
# 1 -- the three match rates
# ---------------------------------------------------------------------------
def fig_match_rates(out):
    """One bar, three segments -- what the 34,392 modeling rows actually are.

    The earlier version drew three bars for three denominators (21,832 / 25,577 /
    34,392) sharing one numerator. That asks the reader to hold three overlapping
    populations in their head at once, which is the confusion it was meant to fix.
    There is only one population; the competing 'match rates' are just arithmetic
    over these segments, so draw the segments and let the rates be spoken.
    """
    segs = [
        ("Matched to an NU org record", 16111, VIOLET, "white"),
        ("School record, no org match", 5721, "#b3a9e2", INK),
        ("Org record only — no school to match", 12560, SHELL, INK2),
    ]
    total = sum(n for _, n, _, _ in segs)

    fig, ax = plt.subplots(figsize=(11.5, 2.9))
    left = 0
    for label, n, color, tc in segs:
        ax.barh(0, n, left=left, color=color, height=0.42)
        ax.text(left + n / 2, 0, f"{n:,}", ha="center", va="center",
                color=tc, fontsize=13, fontweight="bold")
        ax.text(left + n / 2, 0.30, label, ha="center", va="bottom",
                color=INK, fontsize=9.5)
        ax.text(left + n / 2, -0.30, f"{100*n/total:.0f}%", ha="center", va="top",
                color=INK2, fontsize=10)
        left += n

    ax.set_xlim(0, total)
    ax.set_ylim(-0.75, 0.75)
    ax.set_yticks([])
    ax.set_xticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    _title(ax, f"Composition of the {total:,} modeling rows")
    fig.tight_layout()
    _save(fig, out)


# ---------------------------------------------------------------------------
# 2 -- feature coverage, public vs private
# ---------------------------------------------------------------------------
def fig_coverage(out):
    cov = pd.read_csv(COVERAGE).iloc[::-1].reset_index(drop=True)
    y = np.arange(len(cov))
    h = 0.36

    fig, ax = plt.subplots(figsize=(11, 7.6))
    ax.barh(y + h / 2 + 0.02, cov["public_pct"], height=h, color=VIOLET, label="Public")
    ax.barh(y - h / 2 - 0.02, cov["private_pct"], height=h, color=ORANGE, label="Private")

    for yi, (pub, priv) in enumerate(zip(cov["public_pct"], cov["private_pct"])):
        ax.text(pub + 1.2, yi + h / 2 + 0.02, f"{pub:.0f}", va="center", fontsize=8.6, color=INK2)
        ax.text(priv + 1.2, yi - h / 2 - 0.02, f"{priv:.0f}", va="center", fontsize=8.6,
                color=MUTED if priv == 0 else INK2)

    ax.set_yticks(y)
    ax.set_yticklabels(cov["feature"], fontsize=9.5, color=INK)
    ax.set_xlim(0, 104)
    ax.xaxis.set_major_formatter(PercentFormatter())
    _style(ax, grid_axis="x")
    # top rows are the shortest bars, so the upper right is the only clear corner
    ax.legend(loc="upper right", frameon=False, fontsize=10, labelcolor=INK2)

    last = None
    for i, g in enumerate(cov["group"]):
        if g != last and i:
            ax.axhline(i - 0.5, color=GRID, lw=1)
        last = g

    _title(ax, "Feature coverage by sector")
    fig.tight_layout()
    _save(fig, out)


# ---------------------------------------------------------------------------
# 3 -- AP efficiency
# ---------------------------------------------------------------------------
def fig_efficiency(out):
    anal = pd.read_csv(ANALYSIS, low_memory=False)
    d = anal.dropna(subset=["ap_tests_offered", "ap_score_nu"]).copy()
    med_off, med_sc = d["ap_tests_offered"].median(), d["ap_score_nu"].median()
    se = d["ap_efficiency_quadrant"].str.startswith("Selective", na=False)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.6), gridspec_kw={"width_ratios": [1.5, 1]})

    ax = axes[0]
    ax.scatter(d.loc[~se, "ap_tests_offered"], d.loc[~se, "ap_score_nu"],
               s=7, alpha=0.15, color=MUTED, edgecolors="none")
    ax.scatter(d.loc[se, "ap_tests_offered"], d.loc[se, "ap_score_nu"],
               s=11, alpha=0.5, color=AQUA, edgecolors="none")
    ax.axvline(med_off, color=GRID, lw=1.2)
    ax.axhline(med_sc, color=GRID, lw=1.2)
    ax.set_xlabel("AP courses offered", fontsize=9.5, color=INK2)
    ax.set_ylabel("Mean AP exam score (1–5)", fontsize=9.5, color=INK2)
    _style(ax, grid_axis=None)
    _title(ax, "Mean AP exam score by AP courses offered", size=12)

    ax2 = axes[1]
    by_tier = (anal.loc[anal["ap_efficiency_quadrant"].str.startswith("Selective", na=False),
                        "rigor_tier_label"].value_counts().reindex(TIERS).fillna(0))
    ax2.barh(range(5), by_tier.values, color=["#d8d6d0"] * 4 + [AQUA], height=0.62)
    for i, v in enumerate(by_tier.values):
        ax2.text(v + 14, i, f"{int(v):,}", va="center", fontsize=10, color=INK)
    ax2.set_yticks(range(5))
    ax2.set_yticklabels(TIERS, fontsize=9.8, color=INK)
    ax2.invert_yaxis()
    ax2.set_xlim(0, by_tier.max() * 1.18)
    _style(ax2, grid_axis="x")
    _title(ax2, "Selective & effective schools by rigor tier", size=12)

    fig.tight_layout()
    _save(fig, out)


# ---------------------------------------------------------------------------
# 4 -- nominal vs effective weights + sensitivity
# ---------------------------------------------------------------------------
PRETTY = {"ap_opportunity": "AP opportunity", "ap_performance": "AP performance",
          "crdc_coursework": "CRDC coursework", "test_participation": "Test participation",
          "test_performance": "Test performance"}
SCHEME_PRETTY = {"equal": "Equal weights", "availability_only": "Drop performance",
                 "performance_heavy": "Performance-heavy", "ib_included": "IB weighted separately"}


def fig_weights(out):
    df = pd.read_csv(MODELING, low_memory=False)
    comp = rc.build_components(df, rc.COMPONENT_SPECS["v4"])
    weights = rc.WEIGHT_SCHEMES[rc.DEFAULT_SCHEME]
    _, avail = rc.weighted_composite(comp, weights)
    active = [n for n, w in weights.items() if w > 0]
    eff, _, n_full = rc.effective_weights(comp, weights, avail[active].all(axis=1))

    order = sorted(active, key=lambda n: eff[n])
    y = np.arange(len(order))

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.4), gridspec_kw={"width_ratios": [1.1, 1]})

    ax = axes[0]
    for yi, name in zip(y, order):
        nom, e = weights[name], eff[name]
        ax.plot([nom, e], [yi, yi], color=GRID, lw=3, zorder=1, solid_capstyle="round")
        ax.scatter(nom, yi, s=105, color=VIOLET, zorder=3, edgecolors="white", lw=1.6)
        ax.scatter(e, yi, s=105, color=ORANGE, zorder=3, edgecolors="white", lw=1.6)
        ax.text(max(nom, e) + 0.014, yi, f"{e - nom:+.2f}", va="center", fontsize=9.5,
                color=ORANGE if e > nom else INK2)
    ax.scatter([], [], s=105, color=VIOLET, label="Assigned")
    ax.scatter([], [], s=105, color=ORANGE, label="Actual")
    ax.set_yticks(y)
    ax.set_yticklabels([PRETTY[n] for n in order], fontsize=10, color=INK)
    ax.set_xlim(0, 0.40)
    ax.set_ylim(-1.05, len(order) - 0.45)
    _style(ax, grid_axis="x")
    ax.legend(loc="lower right", frameon=False, fontsize=9.5, labelcolor=INK2,
              handletextpad=0.4, borderpad=0)
    _title(ax, "Nominal vs. effective component weight", size=12)

    ax2 = axes[1]
    sens = pd.read_csv(SENS).sort_values("pct_schools_changed_tier")
    hero = sens["scheme"] == "availability_only"
    ax2.barh(np.arange(len(sens)), sens["pct_schools_changed_tier"],
             color=[ORANGE if h else "#d8d6d0" for h in hero], height=0.6)
    for yi, pct in enumerate(sens["pct_schools_changed_tier"]):
        ax2.text(pct + 1.0, yi, f"{pct:.0f}%", va="center", fontsize=10, color=INK)
    ax2.set_yticks(np.arange(len(sens)))
    ax2.set_yticklabels([SCHEME_PRETTY.get(s, s) for s in sens["scheme"]], fontsize=10, color=INK)
    ax2.set_xlim(0, 55)
    ax2.xaxis.set_major_formatter(PercentFormatter())
    _style(ax2, grid_axis="x")
    _title(ax2, "Schools changing tier, by weighting scheme", size=12)

    fig.tight_layout()
    _save(fig, out)


# ---------------------------------------------------------------------------
# 5 -- score distribution and the Jenks cuts
# ---------------------------------------------------------------------------
def fig_cutpoints(out):
    rig = pd.read_csv(RIGOR, low_memory=False)
    d = rig.dropna(subset=["rigor_score", "rigor_tier_label"])
    edges = d.groupby("rigor_tier_label")["rigor_score"].agg(["min", "max", "count"]).reindex(TIERS)

    fig, ax = plt.subplots(figsize=(11.5, 5.4))
    lo, hi = -3.3, 4.0
    bins = np.linspace(lo, hi, 150)
    for i, tier in enumerate(TIERS):
        ax.hist(d.loc[d["rigor_tier_label"] == tier, "rigor_score"], bins=bins,
                color=TIER_RAMP[i], label=tier)

    for c in edges["min"].tolist()[1:]:
        ax.axvline(c, color=INK, lw=1, ls=(0, (4, 3)), zorder=5)

    ymax = ax.get_ylim()[1]
    for i, tier in enumerate(TIERS):
        mid = np.clip((max(edges.loc[tier, "min"], lo) + min(edges.loc[tier, "max"], hi)) / 2, lo, hi)
        ax.text(mid, ymax * 0.94, f"{int(edges.loc[tier, 'count']):,}", ha="center",
                fontsize=10.5, color=INK, fontweight="bold")

    ax.set_xlim(lo, hi)
    ax.set_xlabel("rigor_score", fontsize=9.5, color=INK2)
    _style(ax, grid_axis="y")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=5, frameon=False,
              fontsize=9.5, labelcolor=INK2, handlelength=1.1, columnspacing=1.8)
    _title(ax, "Rigor score distribution, by tier")
    fig.tight_layout()
    _save(fig, out)


# ---------------------------------------------------------------------------
# 6 -- validated against independent SAT
# ---------------------------------------------------------------------------
def fig_validation(out):
    bench = pd.read_csv(BENCH, low_memory=False)
    g = (bench.dropna(subset=["sat_score_nu", "rigor_tier_label"])
         .groupby("rigor_tier_label")["sat_score_nu"].agg(["mean", "count"]).reindex(TIERS))

    fig, ax = plt.subplots(figsize=(10, 5.4))
    ax.bar(np.arange(5), g["mean"], color=TIER_RAMP, width=0.64)
    for i, (m, n) in enumerate(zip(g["mean"], g["count"])):
        ax.text(i, m + 6, f"{m:,.0f}", ha="center", fontweight="bold", color=INK, fontsize=12)
        ax.text(i, 1010, f"n={int(n):,}", ha="center", color="white" if i >= 3 else INK2, fontsize=9)

    ax.set_xticks(np.arange(5))
    ax.set_xticklabels(TIERS, fontsize=10, color=INK)
    ax.set_ylim(1000, 1320)
    _style(ax, grid_axis="y")
    _title(ax, "Mean SAT by rigor tier")
    fig.tight_layout()
    _save(fig, out)


# ---------------------------------------------------------------------------
# 7 -- data-flow diagram
# ---------------------------------------------------------------------------
def _box(ax, x, y, w, h, text, fc, ec, fs=8.4, tc=INK, weight="normal"):
    ax.add_patch(plt.Rectangle((x, y), w, h, facecolor=fc, edgecolor=ec, lw=1.2, zorder=2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            color=tc, zorder=3, linespacing=1.45, fontweight=weight)


def _arrow(ax, x0, y0, x1, y1):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0), zorder=1,
                arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=1.3, shrinkA=0, shrinkB=0))


def fig_pipeline(out):
    fig, ax = plt.subplots(figsize=(14, 6.0))
    ax.set_xlim(0, 100)
    ax.set_ylim(0.5, 54)
    ax.axis("off")

    for x, title in [(2, "1 · Sources"), (25, "2 · Clean & link"), (48, "3 · Join & freeze"),
                     (69, "4 · Rigor index"), (86, "5 · Analysis")]:
        ax.text(x, 51.5, title, fontsize=10.5, color=INK, fontweight="bold")

    sources = [("NCES CCD + PSS", 43), ("College Board CEEB", 36), ("CRDC 2021-22", 29),
               ("EDFacts 2020-21", 22), ("Census F-33 · SAIPE", 15), ("IBO · ISBE (IL)", 8)]
    for text, y in sources:
        _box(ax, 2, y, 19, 5.2, text, "#f4f2fa", VIOLET)
    _box(ax, 2, 1, 19, 5.2, "NU org export", "#fdeee7", ORANGE, weight="bold")

    _box(ax, 25, 32, 19, 10, "clean_*.py", "#f4f2fa", VIOLET)
    _box(ax, 25, 18, 19, 11, "build_ceeb_crosswalk.py\n+ LLM adjudication", "#f4f2fa", VIOLET)
    _box(ax, 25, 3, 19, 11, "combine_schools.py\n25,577 · 64.5% matched", "#f4f2fa", VIOLET)

    _box(ax, 48, 30, 18, 11, "build_features.py", "#f4f2fa", VIOLET)
    _box(ax, 48, 11, 18, 15, "build_modeling_dataset.py\n\nFROZEN\n34,392 × 66",
         "#ece9f7", VIOLET, weight="bold")

    _box(ax, 69, 20, 15, 16, "build_rigor_\nclassification.py\n\n21,951 scored\n(64%)",
         "#ece9f7", VIOLET, fs=8.6, weight="bold")

    layers = [("benchmarking", 37), ("rigor analysis", 27), ("clustering", 17),
              ("predictive validation", 7)]
    for text, y in layers:
        _box(ax, 86, y, 13, 8, text, "#eafaf3", "#12805a", fs=8.2)

    for _, y in sources:
        _arrow(ax, 21, y + 2.6, 25, 37 if y > 25 else 24)
    _arrow(ax, 21, 3.6, 25, 8.5)
    _arrow(ax, 34.5, 32, 34.5, 29)
    _arrow(ax, 34.5, 18, 34.5, 14)
    _arrow(ax, 44, 8.5, 48, 35)
    _arrow(ax, 57, 30, 57, 26)
    _arrow(ax, 66, 18.5, 69, 28)
    for _, y in layers:
        _arrow(ax, 84, 28, 86, y + 4)

    ax.text(0, 55.5, "ETL pipeline", fontsize=15, color=INK, fontweight="bold")
    _save(fig, out)


# ---------------------------------------------------------------------------
# 8 -- how a score is computed
# ---------------------------------------------------------------------------
def fig_index_schematic(out):
    fig, ax = plt.subplots(figsize=(13.5, 6.0))
    ax.set_xlim(0, 100)
    ax.set_ylim(4.5, 56)
    ax.axis("off")

    comps = [("AP opportunity", "ap_tests_taken\nap_classes_offered\nap_take_rate", 0.25, 41),
             ("AP performance", "ap_qualifying_density", 0.20, 33),
             ("CRDC coursework", "ap_participation\ndual_enrollment_rate\nib_intensity_v2", 0.20, 22),
             ("Test participation", "testtaker_rate\nsat_participation_nu", 0.15, 13),
             ("Test performance", "sat_score_nu\nact_composite_il", 0.20, 5)]

    for x, title in [(1, "1 · Sub-features"), (27, "2 · Standardize"), (44, "3 · Components"),
                     (64, "4 · Composite"), (83, "5 · Tiers")]:
        ax.text(x, 53, title, fontsize=10.5, color=INK, fontweight="bold")

    for name, feats, w, y in comps:
        h = 2.4 + 1.9 * (feats.count("\n") + 1)
        _box(ax, 1, y, 22, h, feats, "#f7f6fb", "#cfcade", fs=8.0, tc=INK2)
        _box(ax, 27, y + h / 2 - 1.9, 13, 3.8, "z-score", "#f4f2fa", VIOLET, fs=8.4)
        _box(ax, 44, y + h / 2 - 2.7, 17, 5.4, f"{name}\n{w:.2f}", "#ece9f7", VIOLET,
             fs=9.0, weight="bold")
        _arrow(ax, 23, y + h / 2, 27, y + h / 2)
        _arrow(ax, 40, y + h / 2, 44, y + h / 2)
        _arrow(ax, 61, y + h / 2, 64, 27)

    _box(ax, 64, 21, 15, 12, "Σ wᵢZᵢ ⁄ Σ wᵢ\n\nover components\nthe school has\n\n→ rigor_score",
         "#ece9f7", VIOLET, fs=8.8, weight="bold")

    tiers = [("Most Demanding", "295"), ("Very Demanding", "2,365"), ("Demanding", "6,490"),
             ("Average", "8,905"), ("Below Average", "3,896")]
    for i, (label, n) in enumerate(tiers):
        y = 39 - i * 6.8
        _box(ax, 83, y, 16, 5.6, f"{label}   n={n}", TIER_RAMP[4 - i], TIER_RAMP[4 - i],
             fs=8.6, tc="white" if i < 2 else INK)
    _arrow(ax, 79, 27, 83, 27)

    ax.text(0, 57.2, "Rigor index construction", fontsize=15, color=INK,
            fontweight="bold")
    _save(fig, out)


# ---------------------------------------------------------------------------
# 9 -- predictive validation
# ---------------------------------------------------------------------------
BLOCK_ORDER = ["SES only", "Opportunity only", "SES + Opportunity"]
SPEC_TITLE = {"main": "Held-out R², all 8 opportunity features",
              "crdc_only": "Held-out R², CRDC-only features"}


def fig_predictive(out):
    met = pd.read_csv(PV_METRICS)
    imp = pd.read_csv(PV_IMPORTANCE).sort_values("importance")
    gbm = met[(met["model"] == "gbm") & (met["block"].isin(BLOCK_ORDER))]

    fig, axes = plt.subplots(1, 3, figsize=(14.5, 5.4), gridspec_kw={"width_ratios": [1, 1, 1.3]})

    for ax, spec in zip(axes[:2], ["main", "crdc_only"]):
        s = gbm[gbm["spec"] == spec].set_index("block").reindex(BLOCK_ORDER)
        ax.bar(range(3), s["r2"], color=["#c9c6c0", ORANGE, VIOLET], width=0.62)
        for i, v in enumerate(s["r2"]):
            ax.text(i, v + 0.008, f"{v:.2f}", ha="center", fontsize=11, color=INK,
                    fontweight="bold")
        ax.set_xticks(range(3))
        ax.set_xticklabels(["SES", "Opportunity", "Both"], fontsize=9.5)
        ax.set_ylim(0, 0.5)
        ax.set_ylabel("Held-out R²", fontsize=9.5, color=INK2)
        _style(ax, grid_axis="y")
        _title(ax, SPEC_TITLE[spec], size=11)

    ax = axes[2]
    ax.barh(range(len(imp)), imp["importance"], height=0.66,
            color=[VIOLET if b == "SES" else ORANGE for b in imp["block"]])
    ax.set_yticks(range(len(imp)))
    ax.set_yticklabels(imp["feature"], fontsize=8.6, color=INK)
    ax.set_xlim(-0.02, 0.6)
    _style(ax, grid_axis="x")
    ax.legend([plt.Rectangle((0, 0), 1, 1, color=VIOLET),
               plt.Rectangle((0, 0), 1, 1, color=ORANGE)],
              ["SES", "Opportunity"], loc="lower right", frameon=False, fontsize=9.5,
              labelcolor=INK2)
    _title(ax, "Permutation importance", size=11)

    fig.tight_layout()
    _save(fig, out)


if __name__ == "__main__":
    plt.rcParams["font.family"] = "DejaVu Sans"
    for fn, name in [
        (fig_match_rates, "match_rates.png"),
        (fig_coverage, "coverage_by_sector.png"),
        (fig_efficiency, "ap_efficiency.png"),
        (fig_weights, "weights.png"),
        (fig_cutpoints, "tier_cutpoints.png"),
        (fig_validation, "rigor_validation.png"),
        (fig_pipeline, "pipeline.png"),
        (fig_index_schematic, "index_schematic.png"),
        (fig_predictive, "predictive_validation.png"),
    ]:
        fn(name)
        print(f"Wrote {name}")
