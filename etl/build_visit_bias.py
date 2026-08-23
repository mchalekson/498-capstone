"""
build_visit_bias.py -- does NU's own recruiting activity determine who the rigor index can score?

WHY THIS EXISTS. The Wk6 client discussion established how the NU-sourced school fields are
maintained: they refresh weekly, but only for schools that have an application in flight. Schools
with no application activity are never touched. That is a coverage mechanism we can test from our
side of the data, because the org export carries exactly one date column -- `Last Visit`, when an
NU representative last visited the school -- which is a direct observable proxy for recruiting
engagement.

WHY IT MATTERS. `ap_qualifying_density` and `sat_score_nu` are NU-sourced, and in the shipped v4
index they are the two components carrying the highest *effective* weight (0.310 and 0.230 --
together ~54% of the composite's variance, see docs/RIGOR_CLASSIFICATION.md). If those fields
populate only where NU already recruits, then the index's dominant signal is available
preferentially at schools NU already knows, and the tier carries a recruiting-footprint bias on
top of whatever socioeconomic bias it has. That is a distinct and separately reportable concern
from the SES check already in the pipeline, and it cuts directly against the discovery-list
story: schools absent from the admissions list are, almost by construction, never-visited.

WHAT IT DOES NOT CLAIM. Visiting a school does not *cause* it to be rigorous. Two channels are
confounded here and this script separates them rather than resolving them:

  (1) SELECTION -- NU visits schools it already believes are strong, so visited schools would
      score higher even with perfect data everywhere.
  (2) MEASUREMENT -- visiting populates the fields that make a school scorable on the
      performance components at all, so never-visited schools fall back to availability-only
      signal and are scored on a different, thinner basis.

Channel (2) is the one we can act on (it is what a dummy-record push would fix) and the one the
full-coverage decomposition below isolates: restricted to schools where *every* component is
present, any remaining gap cannot be a data-availability artifact.

Run:  python build_visit_bias.py rigor_classification_v4_2026-07-24.csv --version v4
"""
import argparse
import datetime as dt
import os

import numpy as np
import pandas as pd

from config import NU_MASTER_PATH

# NU-sourced org fields whose refresh is gated on application activity (client, Wk6).
# Source column name in the export -> the modeling-set name it becomes.
NU_FIELDS = {
    "Avg AP score": "ap_score_nu",
    "Avg Freshman SAT": "sat_score_nu",
    "% students taking AP": "ap_pct_students_nu",
    "Avg # AP tests taken": "ap_tests_taken",
    "% seniors taking SAT": "sat_participation_nu",
}
TIERS = ["Below Average", "Average", "Demanding", "Very Demanding", "Most Demanding"]


def norm_ceeb(s):
    """CEEB is a 6-char zero-padded string; anything that has been through a numeric type has
    lost its leading zeros. Re-pad and keep only well-formed codes."""
    return (s.astype(str).str.replace(r"\.0$", "", regex=True).str.strip().str.zfill(6))


def load_visits(path=NU_MASTER_PATH):
    """`Last Visit` + the gated NU fields, straight from the org export."""
    usecols = ["Last Visit", "CEEB"] + list(NU_FIELDS)
    df = pd.read_excel(path, sheet_name="Export", usecols=usecols,
                       dtype={"CEEB": str})
    df["ceeb"] = norm_ceeb(df["CEEB"])
    df["last_visit"] = pd.to_datetime(df["Last Visit"], errors="coerce")
    df["ever_visited"] = df["last_visit"].notna()
    return df


def field_population(df):
    """Population rate of each gated field, visited vs never-visited orgs."""
    rows = []
    for src, dest in NU_FIELDS.items():
        pop = df[src].notna()
        rows.append({
            "field": dest,
            "source_column": src,
            "pct_populated_visited": round(pop[df.ever_visited].mean() * 100, 1),
            "pct_populated_never_visited": round(pop[~df.ever_visited].mean() * 100, 1),
        })
    out = pd.DataFrame(rows)
    out["gap_pp"] = (out.pct_populated_visited - out.pct_populated_never_visited).round(1)
    return out


def full_coverage_decomposition(m, comp_cols):
    """
    The key test. Restrict to schools where EVERY rigor component is present, so data
    availability is held constant, then re-measure the visited/never-visited score gap.

    Interpretation:
      - gap collapses  -> the headline gap was mostly MEASUREMENT (missing data), which a
                          dummy-record push or a fuller export would fix.
      - gap persists   -> the headline gap is mostly SELECTION (NU visits stronger schools),
                          which is real signal, not an artifact -- but still means the tier
                          encodes NU's recruiting footprint.
    """
    full = m[comp_cols].notna().all(axis=1) if comp_cols else pd.Series(False, index=m.index)
    sub = m[full & m.rigor_score.notna()]
    if sub.empty or sub.ever_visited.nunique() < 2:
        return None
    g = sub.groupby("ever_visited")["rigor_score"].agg(["mean", "median", "size"])
    overall = m[m.rigor_score.notna()].groupby("ever_visited")["rigor_score"].mean()
    return {
        "n_full_coverage_scored": int(len(sub)),
        "mean_visited": round(float(g.loc[True, "mean"]), 3),
        "mean_never_visited": round(float(g.loc[False, "mean"]), 3),
        "gap_full_coverage": round(float(g.loc[True, "mean"] - g.loc[False, "mean"]), 3),
        "gap_all_scored": round(float(overall.loc[True] - overall.loc[False]), 3),
        "n_visited": int(g.loc[True, "size"]),
        "n_never_visited": int(g.loc[False, "size"]),
    }


def make_figure(fieldpop, m, out_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    NAVY, LIGHT, INK = "#4E2A84", "#B6ACD1", "#1A1A1A"
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "axes.titlesize": 12, "axes.titleweight": "bold",
        "axes.titlelocation": "left", "text.color": INK, "axes.edgecolor": "#CCC",
    })
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.4))

    y = np.arange(len(fieldpop))
    ax1.barh(y + 0.19, fieldpop.pct_populated_visited, 0.38, color=NAVY, label="visited by NU")
    ax1.barh(y - 0.19, fieldpop.pct_populated_never_visited, 0.38, color=LIGHT, label="never visited")
    for i, r in fieldpop.reset_index(drop=True).iterrows():
        ax1.text(r.pct_populated_visited + 1.5, i + 0.19, f"{r.pct_populated_visited:.0f}%",
                 va="center", fontsize=9)
        ax1.text(r.pct_populated_never_visited + 1.5, i - 0.19,
                 f"{r.pct_populated_never_visited:.0f}%", va="center", fontsize=9, color="#555")
    ax1.set_yticks(y); ax1.set_yticklabels(fieldpop.field, fontsize=9)
    ax1.set_xlim(0, 108); ax1.set_xlabel("% of orgs with the field populated")
    ax1.set_title("NU-sourced fields populate where NU visits\nthe refresh is gated on application activity")
    ax1.legend(frameon=False, fontsize=9, loc="lower right")
    for s in ("top", "right"): ax1.spines[s].set_visible(False)

    sc = m[m.rigor_tier_label.notna()]
    share = (sc.groupby("rigor_tier_label")["ever_visited"].mean() * 100).reindex(TIERS)
    ax2.bar(range(len(TIERS)), share.values,
            color=[LIGHT, LIGHT, "#836EAA", NAVY, "#2E1150"])
    for i, v in enumerate(share.values):
        ax2.text(i, v + 0.8, f"{v:.1f}%", ha="center", fontsize=10, fontweight="bold")
    ax2.set_xticks(range(len(TIERS)))
    ax2.set_xticklabels([t.replace(" ", "\n") for t in TIERS], fontsize=9)
    ax2.set_ylabel("% of tier ever visited by NU")
    ax2.set_ylim(0, max(share.values) * 1.25)
    ax2.set_title("…and the tier tracks the recruiting footprint\nshare of each tier NU has ever visited")
    for s in ("top", "right"): ax2.spines[s].set_visible(False)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("path", nargs="?", default="rigor_classification_v4_2026-07-24.csv",
                   help="a rigor_classification_*.csv")
    p.add_argument("--version", default="v4")
    p.add_argument("--outdir", default=".")
    p.add_argument("--figdir", default=os.path.join("..", "docs", "fig"))
    args = p.parse_args()

    print(f"Reading org export from {NU_MASTER_PATH} ...")
    v = load_visits()
    print(f"  {len(v):,} org rows; {int(v.ever_visited.sum()):,} "
          f"({v.ever_visited.mean()*100:.1f}%) have ever been visited")

    print("\n[when NU visits] Last Visit by year")
    by_year = v.loc[v.ever_visited, "last_visit"].dt.year.value_counts().sort_index()
    print(by_year.to_string())

    print("\n[the refresh gate] population of NU-sourced fields, visited vs never-visited")
    fieldpop = field_population(v)
    print(fieldpop.to_string(index=False))

    rig = pd.read_csv(args.path, low_memory=False)
    rig["ceeb"] = norm_ceeb(rig["ceeb"])
    vk = v.loc[v.ceeb.str.match(r"^\d{6}$"), ["ceeb", "ever_visited", "last_visit"]] \
          .drop_duplicates("ceeb")
    m = rig.merge(vk, on="ceeb", how="left")
    m["ever_visited"] = m["ever_visited"].fillna(False).astype(bool)
    print(f"\n[join] {len(m):,} school rows; {int(m.ever_visited.sum()):,} matched to a visited org")

    print("\n[scorability] can the index score the school at all?")
    scor = m.groupby("ever_visited")["rigor_score"].apply(lambda s: s.notna().mean() * 100)
    for k in (True, False):
        lbl = "visited    " if k else "never visited"
        print(f"   {lbl}: {scor.loc[k]:.1f}% scored  (n={int((m.ever_visited==k).sum()):,})")

    print("\n[score gap] among schools that ARE scored")
    print(m[m.rigor_score.notna()].groupby("ever_visited")["rigor_score"]
          .agg(["mean", "median", "size"]).round(3).to_string())

    print("\n[tier distribution] row % within visited / never-visited")
    ct = pd.crosstab(m.ever_visited, m.rigor_tier_label, normalize="index") * 100
    print(ct.reindex(columns=[c for c in TIERS if c in ct.columns]).round(1).to_string())

    print("\n[recruiting footprint] share of each tier NU has ever visited")
    sc = m[m.rigor_tier_label.notna()]
    print((sc.groupby("rigor_tier_label")["ever_visited"].mean() * 100)
          .reindex(TIERS).round(1).to_string())

    # Held-constant test: does the gap survive when every component is present?
    comp_cols = [c for c in ["ap_tests_taken", "number_of_ap_classes_offered_mid", "ap_take_rate",
                             "ap_qualifying_density", "ap_participation", "dual_enrollment_rate",
                             "testtaker_rate", "sat_participation_nu", "sat_score_nu"]
                 if c in m.columns]
    print("\n[decomposition] selection vs measurement -- gap on the full-coverage subset")
    dec = full_coverage_decomposition(m, comp_cols)
    if dec:
        for k, val in dec.items():
            print(f"   {k}: {val}")
        share_expl = 1 - (dec["gap_full_coverage"] / dec["gap_all_scored"]) \
            if dec["gap_all_scored"] else float("nan")
        print(f"   -> {share_expl*100:.0f}% of the headline gap disappears once data availability "
              f"is held constant (the MEASUREMENT channel); the remainder is SELECTION.")
    else:
        print("   insufficient full-coverage rows to decompose")

    print("\n[is 'visited' just affluence?] mean county child poverty")
    if "child_poverty_saipe" in m.columns:
        print(m.groupby("ever_visited")["child_poverty_saipe"].agg(["mean", "size"]).round(2).to_string())

    os.makedirs(args.figdir, exist_ok=True)
    fig_path = os.path.join(args.figdir, "visit_bias.png")
    make_figure(fieldpop, m, fig_path)
    print(f"\nWrote {fig_path}")

    date_tag = dt.date.today().isoformat()
    out_path = os.path.join(args.outdir, f"visit_bias_{args.version}_{date_tag}.csv")
    m[["ceeb", "school_name", "state", "ever_visited", "last_visit", "rigor_score",
       "rigor_tier_label", "rigor_n_components_used"]].to_csv(out_path, index=False)
    print(f"Wrote {out_path} ({len(m):,} rows)")
