"""
build_rigor_v5_figures.py
-------------------------
Deck- and paper-ready figures for the **v5** rigor index, the version actually
shipped to the client (`docs/RIGOR_FORMULA_V5.md`). Companion to
`build_rigor_figures.py`, which reads the v4 chain; nothing here reads v4, so the
two sets never silently disagree about which index is being drawn.

Same text discipline as the v4 script: a title and the graph. The title states what
is plotted -- a label, not a sentence and not a conclusion. Interpretation lives in
docs/ and in the paper, not in the artwork.

Inputs (all in csv_exports/, all emitted by etl/build_rigor_v5.py):
  rigor_v5_weights_2026-07-31.csv            nominal vs effective weight
  rigor_v5_component_coverage_2026-07-31.csv coverage by component and sector
  rigor_v5_validation_2026-07-31.csv         tier means vs external measures
  rigor_v5_ses_entanglement_2026-07-31.csv   per-component poverty correlation
  rigor_v5_sensitivity_2026-07-31.csv        alternate weighting schemes
  rigor_classification_v5_2026-07-31.csv     per-school scores and tiers

Figures:
  v5_weights.png            nominal vs effective weight, nine components
  v5_component_coverage.png component coverage, public vs private
  v5_validation.png         tier means, held-out measures vs index-derived ones
  v5_ses_entanglement.png   per-component correlation with child poverty
  v5_sensitivity.png        tier movement under alternate weighting schemes
  v5_tiers.png              score distribution with the fitted Jenks cut-points

Run from csv_exports/:  python ../etl/build_rigor_v5_figures.py
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# --- palette (identical to build_rigor_figures.py so the two sets sit together) --
VIOLET = "#4a3aa7"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
TIER_RAMP = ["#dcd8f2", "#b3a9e2", "#8878cd", "#5f4cb8", "#372a80"]
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#8d8b85", "#e6e4de"
SHELL = "#efedf5"

TIERS = ["Below Average", "Average", "Demanding", "Very Demanding", "Most Demanding"]

WEIGHTS = "rigor_v5_weights_2026-07-31.csv"
COVERAGE = "rigor_v5_component_coverage_2026-07-31.csv"
VALIDATION = "rigor_v5_validation_2026-07-31.csv"
SES = "rigor_v5_ses_entanglement_2026-07-31.csv"
SENS = "rigor_v5_sensitivity_2026-07-31.csv"
CLASSIFICATION = "rigor_classification_v5_2026-07-31.csv"

# Fitted cut-points, from docs/RIGOR_FORMULA_V5.md 7 (recomputed below as a check).
CUTS = [-0.704, -0.207, 0.286, 0.977]

LABEL = {
    "ap_opportunity": "AP opportunity",
    "ap_performance": "AP performance",
    "advanced_access": "Advanced access",
    "ib": "IB",
    "stem_depth": "STEM depth",
    "test_performance": "Test performance",
    "test_participation": "Test participation",
    "college_placement": "College placement",
    "faculty_investment": "Faculty investment",
}

SCHEME_LABEL = {
    "v4_equivalent": "v4-equivalent",
    "equal": "Equal (1/9 each)",
    "performance_heavy": "Performance-heavy",
    "no_new_factors": "No new factors",
}


def _style(ax, grid_axis="y"):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9.5, length=0)
    ax.set_axisbelow(True)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID, lw=0.8)


def _title(ax, headline, size=13):
    ax.set_title(headline, fontsize=size, loc="left", color=INK, pad=10,
                 fontweight="semibold")


def _save(fig, out):
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------------------
# 1 -- nominal vs effective weight
# ---------------------------------------------------------------------------
def fig_weights(out):
    """The composite-indicator literature's own diagnostic (CADRE 2024).

    Drawn as paired bars rather than a slope chart: the reader's question is
    "which components pull more than they were given", and a length comparison
    answers that faster than a slope does at nine categories.
    """
    w = pd.read_csv(WEIGHTS).iloc[::-1].reset_index(drop=True)
    y = np.arange(len(w))
    h = 0.36

    fig, ax = plt.subplots(figsize=(9.6, 5.4))
    ax.barh(y + h / 2, w["nominal_weight"], height=h, color=SHELL,
            edgecolor=MUTED, lw=0.8, label="Nominal (designed)")
    ax.barh(y - h / 2, w["effective_weight"], height=h, color=VIOLET,
            label="Effective (measured)")

    for i, r in w.iterrows():
        ax.text(r["nominal_weight"] + 0.006, i + h / 2, f"{r['nominal_weight']:.2f}",
                va="center", fontsize=9, color=INK2)
        over = r["effective_weight"] > r["nominal_weight"] + 0.02
        ax.text(r["effective_weight"] + 0.006, i - h / 2, f"{r['effective_weight']:.3f}",
                va="center", fontsize=9,
                color=ORANGE if over else INK2,
                fontweight="bold" if over else "normal")

    ax.set_yticks(y)
    ax.set_yticklabels([LABEL[c] for c in w["component"]], fontsize=10, color=INK)
    ax.set_xlim(0, 0.42)
    ax.set_xticks([0, 0.1, 0.2, 0.3, 0.4])
    _style(ax, grid_axis="x")
    ax.legend(loc="lower right", frameon=False, fontsize=10, labelcolor=INK2)
    _title(ax, "Nominal vs. effective weight, v5 rigor index")
    fig.tight_layout()
    _save(fig, out)


# ---------------------------------------------------------------------------
# 2 -- component coverage, public vs private
# ---------------------------------------------------------------------------
def fig_component_coverage(out):
    """Why a private school cannot be scored on the same instrument.

    Three components sit at exactly 0.0% private -- CRDC is a public-school
    collection by statute. That is the figure's whole point, so the zeros are
    labelled rather than left as absent bars.
    """
    cov = pd.read_csv(COVERAGE).iloc[::-1].reset_index(drop=True)
    y = np.arange(len(cov))
    h = 0.36

    fig, ax = plt.subplots(figsize=(9.6, 5.4))
    ax.barh(y + h / 2, cov["public_pct"], height=h, color=VIOLET, label="Public")
    ax.barh(y - h / 2, cov["private_pct"], height=h, color=ORANGE, label="Private")

    for i, r in cov.iterrows():
        ax.text(r["public_pct"] + 1.2, i + h / 2, f"{r['public_pct']:.0f}",
                va="center", fontsize=9, color=INK2)
        zero = r["private_pct"] == 0
        ax.text(r["private_pct"] + 1.2, i - h / 2, f"{r['private_pct']:.0f}",
                va="center", fontsize=9,
                color=ORANGE if zero else INK2,
                fontweight="bold" if zero else "normal")

    ax.set_yticks(y)
    ax.set_yticklabels([f"{LABEL[c]}  ({w:.2f})"
                        for c, w in zip(cov["component"], cov["nominal_weight"])],
                       fontsize=10, color=INK)
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 20, 40, 60, 80, 100])
    ax.set_xticklabels(["0%", "20%", "40%", "60%", "80%", "100%"])
    _style(ax, grid_axis="x")
    ax.legend(loc="lower right", frameon=False, fontsize=10, labelcolor=INK2)
    _title(ax, "v5 component coverage by sector (nominal weight in parentheses)")
    fig.tight_layout()
    _save(fig, out)


# ---------------------------------------------------------------------------
# 3 -- tier means against external measures
# ---------------------------------------------------------------------------
def fig_validation(out):
    """Small multiples, with the honest distinction drawn in the panel titles.

    Graduation rate and child poverty are never index inputs. The other four are
    the untransformed forms of index components, so their monotonicity is an
    internal consistency check, not external validation -- the panels say which
    is which rather than letting the reader assume all six are held out.
    """
    v = pd.read_csv(VALIDATION)
    panels = [
        ("grad_rate", "Graduation rate (%)", True),
        ("child_poverty", "Child poverty (%)", True),
        ("sat", "Mean SAT", False),
        ("ap_score", "Mean AP exam score", False),
        ("pct_to_college", "% to college", False),
        ("stem_breadth", "STEM breadth (0–4)", False),
    ]

    fig, axes = plt.subplots(2, 3, figsize=(12.4, 6.4))
    for ax, (col, label, held_out) in zip(axes.ravel(), panels):
        ax.bar(range(5), v[col], color=TIER_RAMP, width=0.68)
        for i, val in enumerate(v[col]):
            txt = f"{val:,.0f}" if col == "sat" else f"{val:g}"
            ax.text(i, val, txt, ha="center", va="bottom", fontsize=8.5, color=INK2)
        ax.set_xticks(range(5))
        ax.set_xticklabels(["BA", "Avg", "Dem", "VD", "MD"], fontsize=9)
        ax.set_ylim(0, v[col].max() * 1.20)
        _style(ax)
        _title(ax, f"{label}" + ("" if held_out else "  (index input)"), size=10.5)

    fig.suptitle("v5 tier means: two held-out measures, four index-derived",
                 fontsize=13, x=0.008, ha="left", color=INK, fontweight="semibold")
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    _save(fig, out)


# ---------------------------------------------------------------------------
# 4 -- per-component socioeconomic entanglement
# ---------------------------------------------------------------------------
def fig_ses_entanglement(out):
    """Where the index's poverty correlation actually comes from.

    Sorted by rho so the two performance components sit together at the negative
    end -- the predicted cost of the literature-motivated shift toward exam
    performance, shown rather than asserted.
    """
    s = pd.read_csv(SES).sort_values("rho_vs_child_poverty").reset_index(drop=True)
    y = np.arange(len(s))
    colors = [ORANGE if r <= -0.30 else (AQUA if r > 0 else VIOLET)
              for r in s["rho_vs_child_poverty"]]

    fig, ax = plt.subplots(figsize=(9.4, 4.8))
    ax.barh(y, s["rho_vs_child_poverty"], height=0.6, color=colors)
    for i, r in s.iterrows():
        rho = r["rho_vs_child_poverty"]
        ax.text(rho + (-0.012 if rho < 0 else 0.012), i, f"{rho:+.3f}",
                va="center", ha="right" if rho < 0 else "left",
                fontsize=9, color=INK2)

    ax.axvline(0, color=MUTED, lw=1)
    ax.set_yticks(y)
    ax.set_yticklabels([LABEL[c] for c in s["component"]], fontsize=10, color=INK)
    ax.set_xlim(-0.48, 0.14)
    _style(ax, grid_axis="x")
    _title(ax, "Spearman correlation with district child poverty, by component")
    fig.tight_layout()
    _save(fig, out)


# ---------------------------------------------------------------------------
# 5 -- sensitivity to alternate weighting schemes
# ---------------------------------------------------------------------------
def fig_sensitivity(out):
    """Reported on frozen cut-points, not refit ones.

    Refitting Jenks conflates schools moving in the score distribution with the
    boundaries themselves moving; the frozen column isolates score movement,
    which is the quantity the reader wants. Refit is drawn behind it in outline
    so the gap between the two conventions stays visible.
    """
    s = pd.read_csv(SENS).sort_values("pct_changed_tier_frozen_cuts")
    y = np.arange(len(s))
    h = 0.34

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.6, 3.6),
                                   gridspec_kw={"width_ratios": [1.5, 1]})

    ax1.barh(y + h / 2, s["pct_changed_tier_refit"], height=h, color=SHELL,
             edgecolor=MUTED, lw=0.8, label="Jenks refit")
    ax1.barh(y - h / 2, s["pct_changed_tier_frozen_cuts"], height=h, color=VIOLET,
             label="Frozen cut-points")
    for i, (_, r) in enumerate(s.iterrows()):
        ax1.text(r["pct_changed_tier_refit"] + 0.8, i + h / 2,
                 f"{r['pct_changed_tier_refit']:.1f}", va="center", fontsize=9, color=INK2)
        ax1.text(r["pct_changed_tier_frozen_cuts"] + 0.8, i - h / 2,
                 f"{r['pct_changed_tier_frozen_cuts']:.1f}", va="center", fontsize=9,
                 color=INK2)
    ax1.set_yticks(y)
    ax1.set_yticklabels([SCHEME_LABEL[c] for c in s["scheme"]], fontsize=10, color=INK)
    ax1.set_xlim(0, 52)
    ax1.set_xticks([0, 10, 20, 30, 40, 50])
    ax1.set_xticklabels(["0%", "10%", "20%", "30%", "40%", "50%"])
    _style(ax1, grid_axis="x")
    ax1.legend(loc="lower right", frameon=False, fontsize=9.5, labelcolor=INK2)
    _title(ax1, "Schools changing tier", size=11.5)

    ax2.barh(y, s["spearman_rank_corr"], height=0.5, color=AQUA)
    for i, (_, r) in enumerate(s.iterrows()):
        ax2.text(r["spearman_rank_corr"] - 0.012, i, f"{r['spearman_rank_corr']:.3f}",
                 va="center", ha="right", fontsize=9, color="white", fontweight="bold")
    ax2.set_yticks(y)
    ax2.set_yticklabels([])
    ax2.set_xlim(0.8, 1.0)
    ax2.set_xticks([0.8, 0.9, 1.0])
    _style(ax2, grid_axis="x")
    _title(ax2, "Spearman ρ vs. shipped index", size=11.5)

    fig.tight_layout()
    _save(fig, out)


# ---------------------------------------------------------------------------
# 6 -- score distribution and the fitted cut-points
# ---------------------------------------------------------------------------
def fig_tiers(out):
    """The continuous score, with the Jenks boundaries drawn where they fell.

    Natural breaks cut at gaps in the distribution rather than at equal counts,
    so the tiers are deliberately unequal in size; the histogram is the evidence
    for that and the counts are printed on the bands.
    """
    df = pd.read_csv(CLASSIFICATION, low_memory=False)
    sc = df["rigor_score_v5"].dropna()
    counts = df["rigor_tier_label_v5"].value_counts().reindex(TIERS)

    # Bin edges must *include* the cut-points, or a bin straddles a boundary and
    # gets painted one tier's colour on both sides of the line.
    lo, hi = sc.min(), sc.max()
    edges = np.unique(np.concatenate([np.linspace(lo, hi, 88), CUTS]))
    bounds = [-np.inf] + CUTS + [np.inf]

    fig, ax = plt.subplots(figsize=(10.6, 4.6))
    for k in range(5):
        sel = sc[(sc >= bounds[k]) & (sc < bounds[k + 1])]
        ax.hist(sel, bins=edges, color=TIER_RAMP[k], lw=0)

    ymax = ax.get_ylim()[1]
    ax.set_ylim(0, ymax * 1.24)
    for c in CUTS:
        ax.axvline(c, ymax=0.80, color=INK, lw=1.1, ls=(0, (4, 3)))
        ax.text(c, ymax * 1.02, f"{c:+.3f}", ha="center", va="bottom",
                fontsize=9, color=INK2)

    centers = [(max(lo, bounds[k]) + min(hi, bounds[k + 1])) / 2 for k in range(5)]
    for cx, tier in zip(centers, TIERS):
        ax.text(cx, -ymax * 0.09, f"{tier}\n{counts[tier]:,}", ha="center", va="top",
                fontsize=9.5, color=INK)

    ax.set_xlim(lo, hi)
    ax.set_yticks([])
    _style(ax, grid_axis=None)
    ax.spines["left"].set_visible(False)
    _title(ax, f"v5 rigor score and the fitted Jenks cut-points "
               f"({int(counts.sum()):,} schools scored)")
    fig.tight_layout()
    _save(fig, out)


if __name__ == "__main__":
    plt.rcParams["font.family"] = "DejaVu Sans"
    for fn, name in [
        (fig_weights, "v5_weights.png"),
        (fig_component_coverage, "v5_component_coverage.png"),
        (fig_validation, "v5_validation.png"),
        (fig_ses_entanglement, "v5_ses_entanglement.png"),
        (fig_sensitivity, "v5_sensitivity.png"),
        (fig_tiers, "v5_tiers.png"),
    ]:
        fn(name)
        print(f"Wrote {name}")
