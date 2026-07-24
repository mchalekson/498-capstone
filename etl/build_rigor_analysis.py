"""
build_rigor_analysis.py -- two Week-5 client ideas, as analysis layers on top of the rigor tier.

(1) AP EFFICIENCY -- Bob's "low AP offering / high AP scores" idea. The rigor composite ADDS
    offering breadth and exam performance (both raise the tier independently), so a big school
    offering 25 APs at mediocre scores outranks a small school offering 5 APs where kids ace
    them. Bob's interest is the school that punches ABOVE its offering weight. This computes an
    efficiency signal -- z(AP exam score) - z(AP tests offered) -- and a 2x2 quadrant, so those
    "small but effective" schools become visible instead of being averaged away.

(2) VALIDATION / CONTEXT -- grad rate and advanced-STEM availability by rigor tier. Both are
    things Bob named as school-comparison signals. They are deliberately NOT folded into the
    composite: grad rate is an SES-confounded OUTCOME (report Week-6 plan holds it OUT as a
    validation check, per the SEDA caution in the lit review); STEM availability is public-only
    CRDC AVAILABILITY (the weak signal per Geiser & Santelices, and ~0% for private schools).
    Used here as an independent check: if the tier is meaningful, grad rate and STEM breadth
    should rise with it -- without either having been an input.

Reads a rigor_classification_*.csv (needs ap_score_nu, ap_tests_offered, rigor_tier_*,
grad_rate_2021, ceeb). STEM is joined from crdc_stem_clean.csv via the ceeb<->nces_id_12 map
in schools_org_all.csv (all three expected next to the rigor file, i.e. in csv_exports/).

Run:  python build_rigor_analysis.py rigor_classification_v3_2026-07-24.csv --version v3
"""
import argparse
import datetime as dt
import os

import numpy as np
import pandas as pd

TIER_ORDER = ["Below Average", "Average", "Demanding", "Very Demanding", "Most Demanding"]
SCORE_COL = "ap_score_nu"
OFFER_COL = "ap_tests_offered"


def keyify(s):
    """Normalize a CEEB column (float/str/mixed) to a clean string join key."""
    return pd.to_numeric(s, errors="coerce").astype("Int64").astype(str).replace("<NA>", np.nan)


def zscore(s):
    s = pd.to_numeric(s, errors="coerce")
    sd = s.std()
    return (s - s.mean()) / sd if sd and not np.isnan(sd) else pd.Series(np.nan, index=s.index)


def ap_efficiency(df):
    """z(exam score) - z(tests offered): high => performance outruns breadth (the Bob case)."""
    both = df[SCORE_COL].notna() & df[OFFER_COL].notna()
    eff = pd.Series(np.nan, index=df.index)
    eff[both] = (zscore(df.loc[both, SCORE_COL]) - zscore(df.loc[both, OFFER_COL]))
    # 2x2 quadrant on medians among schools with both signals
    med_score = df.loc[both, SCORE_COL].median()
    med_offer = df.loc[both, OFFER_COL].median()
    hi_score = df[SCORE_COL] >= med_score
    hi_offer = df[OFFER_COL] >= med_offer
    quad = pd.Series(pd.NA, index=df.index, dtype="object")
    quad[both & ~hi_offer & hi_score] = "Selective & effective (few offered, high scores)"
    quad[both & hi_offer & hi_score] = "Broad & high-performing"
    quad[both & hi_offer & ~hi_score] = "Broad but underperforming"
    quad[both & ~hi_offer & ~hi_score] = "Limited (few offered, low scores)"
    return eff, quad, both.sum()


def join_stem(df, base_dir):
    """Attach advanced-STEM availability via ceeb -> nces_id_12 (schools_org_all) -> crdc_stem."""
    stem_path = os.path.join(base_dir, "crdc_stem_clean.csv")
    all_path = os.path.join(base_dir, "schools_org_all.csv")
    if not (os.path.exists(stem_path) and os.path.exists(all_path)):
        print(f"[stem] crdc_stem_clean.csv / schools_org_all.csv not found in {base_dir} -- skipping STEM")
        for c in ["stem_advanced_offered", "calculus_offered", "physics_offered"]:
            df[c] = np.nan
        return df
    stem = pd.read_csv(stem_path, dtype={"nces_id_12": str}, low_memory=False)
    xwalk = pd.read_csv(all_path, usecols=["ceeb", "nces_id_12"], low_memory=False)
    xwalk["_k"] = keyify(xwalk["ceeb"])
    xwalk = xwalk.dropna(subset=["_k", "nces_id_12"]).drop_duplicates("_k")
    xwalk["nces_id_12"] = xwalk["nces_id_12"].astype(str).str.replace(r"\.0$", "", regex=True)
    stem_cols = ["stem_advanced_offered", "calculus_offered", "physics_offered"]
    stem = stem[["nces_id_12"] + stem_cols]
    m = xwalk.merge(stem, on="nces_id_12", how="left")[["_k"] + stem_cols]
    df = df.copy()
    df["_k"] = keyify(df["ceeb"])
    df = df.merge(m, on="_k", how="left").drop(columns="_k")
    return df


def by_tier(df, col):
    t = df.dropna(subset=["rigor_tier_label"]).copy()
    g = t.groupby("rigor_tier_label")[col].agg(["mean", "count"]).reindex(TIER_ORDER).round(2)
    return g


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="rigor_classification_v3_2026-07-24.csv")
    parser.add_argument("--version", default="v3")
    parser.add_argument("--outdir", default=".")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(args.path))
    df = pd.read_csv(args.path, low_memory=False)
    print(f"Loaded {args.path}: {len(df):,} rows")

    # (1) AP efficiency
    df["ap_efficiency"], df["ap_efficiency_quadrant"], n_both = ap_efficiency(df)
    print("\n" + "=" * 72)
    print("(1) AP EFFICIENCY -- 'low offering / high scores' (Bob, Wk5)")
    print("=" * 72)
    print(f"Computed on {n_both:,} schools with both AP exam score and AP tests offered.")
    print("\n[quadrant distribution]")
    print(df["ap_efficiency_quadrant"].value_counts().to_string())
    print("\n[quadrant x rigor tier -- what the tier's additive ordering hides]")
    ct = pd.crosstab(df["ap_efficiency_quadrant"], df["rigor_tier_label"]).reindex(columns=TIER_ORDER)
    print(ct.to_string())
    print("\n[the Bob case: 'Selective & effective' schools by tier] -- schools offering few APs "
          "but\nscoring high; note how many sit BELOW the top tier despite strong exam outcomes:")
    sel = df[df["ap_efficiency_quadrant"].str.startswith("Selective", na=False)]
    print(sel["rigor_tier_label"].value_counts().reindex(TIER_ORDER).to_string())

    # (2) validation: grad rate + STEM by tier
    df = join_stem(df, base_dir)
    print("\n" + "=" * 72)
    print("(2) VALIDATION -- grad rate & advanced-STEM by rigor tier (neither is a model input)")
    print("=" * 72)
    print("\n[graduation rate by rigor tier -- should rise with tier if the tier is meaningful]")
    print(by_tier(df, "grad_rate_2021").to_string())
    print("\n[advanced-STEM courses offered (0-4: Calc/AdvMath/Chem/Physics) by rigor tier]")
    print(by_tier(df, "stem_advanced_offered").to_string())
    print("\n[calculus offered rate by rigor tier]")
    print(by_tier(df, "calculus_offered").to_string())

    date_tag = dt.date.today().isoformat()
    out_path = os.path.join(args.outdir, f"rigor_analysis_{args.version}_{date_tag}.csv")
    keep = ["ceeb", "school_name", "state", "sector", "rigor_tier_label", "rigor_score",
            SCORE_COL, OFFER_COL, "ap_efficiency", "ap_efficiency_quadrant",
            "stem_advanced_offered", "calculus_offered", "physics_offered", "grad_rate_2021"]
    df[[c for c in keep if c in df.columns]].to_csv(out_path, index=False)
    print(f"\nWrote {out_path}")
