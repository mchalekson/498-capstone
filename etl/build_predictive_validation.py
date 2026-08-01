"""
build_predictive_validation.py -- predictive validation of the rigor construct.

Purpose (see docs/PREDICTIVE_VALIDATION.md): NOT a replacement for the rigor index --
a validation of it, in Adelman's (1999, 2006) spirit: he constructed a curriculum-intensity
index and then regressed degree completion on it. Here we test whether the *opportunity-
structure* ingredients of our rigor index predict a real outcome (the four-year
adjusted-cohort graduation rate) beyond what socioeconomic status alone explains
(the confounding check Reardon/SEDA demands).

Design decisions (each literature- or data-motivated):
  1. PREDICTORS = OPPORTUNITY FEATURES ONLY. The rigor index's exam-performance components
     (ap_score_nu, sat_score_nu) are excluded: predicting an outcome from other outcomes
     would make the validation circular. Only what the school OFFERS and who ENGAGES enters.
  2. SES-INCREMENTAL DESIGN. Three nested models: SES-only baseline -> opportunity-only ->
     SES + opportunity. The claim rests on the INCREMENTAL R^2 of opportunity over SES.
  3. TARGET CAVEATS. grad_rate_2021 is a COVID-cohort rate with privacy blurring (many
     values are range midpoints) and a ceiling (median 91). R^2 is expected to be modest;
     a sensitivity restricted to exact (non-range) values is reported.
  4. ECOLOGICAL LEVEL. School-level regression: findings are about schools, not students.
     Public schools only (EDFacts covers no private schools).

Models: OLS linear regression (interpretable coefficients) and HistGradientBoosting
(nonlinear ceiling reference). Metrics: held-out R^2 / RMSE, permutation importance
(test set). Complete-case on the predictor block, consistent with the pipeline's
no-imputation rule; an all-rows HGB run (native NaN handling) is the robustness check.

Run: python build_predictive_validation.py modeling_dataset_v3_2026-07-24.csv
"""
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

SEED = 42
TARGET = "grad_rate_2021"

OPPORTUNITY = [
    "ap_tests_taken", "number_of_ap_classes_offered_mid", "ap_take_rate",   # AP opportunity
    "ap_participation", "dual_enrollment_rate",                              # CRDC coursework
    "testtaker_rate", "sat_participation_nu",                                # test participation
    "ib_flag_v2",                                                            # IB (rescued flag)
]
SES = ["frl_rate", "child_poverty_saipe", "per_resident_child_funding_state_local"]

# Second specification, reported alongside the main one in docs/PREDICTIVE_VALIDATION.md.
# The main spec's complete-case population is bound by NU-export coverage, so it inherits the
# recruiting-universe selection bias. These four features exist for the whole public-school
# CRDC universe, so the spec trades features for a ~4x larger, unbiased population -- if the
# incremental R^2 survives that swap, it isn't an artifact of who NU recruits.
OPPORTUNITY_CRDC = ["ap_participation", "dual_enrollment_rate", "testtaker_rate", "ib_flag_v2"]

SPECS = {"main": OPPORTUNITY, "crdc_only": OPPORTUNITY_CRDC}


def fit_eval(X_tr, X_te, y_tr, y_te, label):
    out = {}
    lr = LinearRegression().fit(X_tr, y_tr)
    hgb = HistGradientBoostingRegressor(random_state=SEED).fit(X_tr, y_tr)
    for name, model in [("linear", lr), ("gbm", hgb)]:
        pred = model.predict(X_te)
        out[name] = {"r2": r2_score(y_te, pred),
                     "rmse": float(np.sqrt(mean_squared_error(y_te, pred)))}
    print(f"{label:28s} n_train={len(X_tr):5d}  "
          f"linear R2={out['linear']['r2']:.3f} RMSE={out['linear']['rmse']:.2f} | "
          f"gbm R2={out['gbm']['r2']:.3f} RMSE={out['gbm']['rmse']:.2f}")
    return out, lr, hgb


def run_spec(df, opportunity, spec_name, metrics, want_detail):
    """Fit the three nested models for one predictor specification."""
    cc = df.dropna(subset=[TARGET] + opportunity + SES)
    print(f"\n--- spec '{spec_name}' ({len(opportunity)} opportunity features) | "
          f"complete-case n={len(cc):,} ---")

    y = cc[TARGET]
    idx_tr, idx_te = train_test_split(cc.index, test_size=0.2, random_state=SEED)
    both = SES + opportunity
    blocks = [("SES only", SES), ("Opportunity only", opportunity), ("SES + Opportunity", both)]

    results, lr_full, hgb_full = {}, None, None
    for label, cols in blocks:
        res, lr, hgb = fit_eval(cc.loc[idx_tr, cols], cc.loc[idx_te, cols],
                                y.loc[idx_tr], y.loc[idx_te], label)
        results[label] = res
        for family in ("linear", "gbm"):
            metrics.append({"spec": spec_name, "block": label, "model": family,
                            "r2": round(res[family]["r2"], 4),
                            "rmse": round(res[family]["rmse"], 3),
                            "n_train": len(idx_tr), "n_test": len(idx_te),
                            "n_complete_case": len(cc)})
        if label == "SES + Opportunity":
            lr_full, hgb_full = lr, hgb

    inc = {f: results["SES + Opportunity"][f]["r2"] - results["SES only"][f]["r2"]
           for f in ("linear", "gbm")}
    print(f"INCREMENTAL R2 of opportunity over SES:  "
          f"linear +{inc['linear']:.3f} | gbm +{inc['gbm']:.3f}")
    for family in ("linear", "gbm"):
        metrics.append({"spec": spec_name, "block": "Incremental (opportunity over SES)",
                        "model": family, "r2": round(inc[family], 4), "rmse": np.nan,
                        "n_train": len(idx_tr), "n_test": len(idx_te),
                        "n_complete_case": len(cc)})

    imp = None
    if want_detail:
        print("\npermutation importance (gbm, SES+Opportunity, test set):")
        pi = permutation_importance(hgb_full, cc.loc[idx_te, both], y.loc[idx_te],
                                    n_repeats=10, random_state=SEED)
        imp = (pd.DataFrame({"feature": both, "importance": pi.importances_mean,
                             "importance_std": pi.importances_std})
               .sort_values("importance", ascending=False))
        imp["block"] = ["SES" if f in SES else "Opportunity" for f in imp["feature"]]
        print(imp.round(3).to_string(index=False))

        print("\nstandardized linear coefficients (SES+Opportunity):")
        Xz = (cc[both] - cc[both].mean()) / cc[both].std()
        lrz = LinearRegression().fit(Xz.loc[idx_tr], y.loc[idx_tr])
        print(pd.Series(lrz.coef_, index=both).round(2).sort_values().to_string())

    return cc, idx_te, both, lr_full, hgb_full, imp


def main(path):
    df = pd.read_csv(path, low_memory=False)
    df = df[df["sector"] == "public"].copy()
    for c in sorted(set(OPPORTUNITY + OPPORTUNITY_CRDC + SES + [TARGET])):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    print(f"public schools: {len(df):,}")

    metrics = []
    cc, idx_te, both, lr_full, hgb_full, imp = run_spec(
        df, OPPORTUNITY, "main", metrics, want_detail=True)
    run_spec(df, OPPORTUNITY_CRDC, "crdc_only", metrics, want_detail=False)

    # sensitivity: HGB on all public rows with a target (native NaN handling)
    allr = df.dropna(subset=[TARGET])
    Xtr, Xte, ytr, yte = train_test_split(allr[both], allr[TARGET], test_size=0.2,
                                          random_state=SEED)
    hgb_all = HistGradientBoostingRegressor(random_state=SEED).fit(Xtr, ytr)
    r2_all = r2_score(yte, hgb_all.predict(Xte))
    print(f"\nrobustness (all {len(allr):,} public rows w/ target, HGB w/ NaN): R2={r2_all:.3f}")
    metrics.append({"spec": "robustness_all_rows", "block": "SES + Opportunity", "model": "gbm",
                    "r2": round(r2_all, 4), "rmse": np.nan, "n_train": len(Xtr),
                    "n_test": len(Xte), "n_complete_case": len(allr)})

    stamp = path.split("_v")[-1].replace(".csv", "")
    out = cc.loc[idx_te, ["ceeb", "school_name", "state", TARGET]].copy()
    out["pred_linear"] = lr_full.predict(cc.loc[idx_te, both])
    out["pred_gbm"] = hgb_full.predict(cc.loc[idx_te, both])
    out["residual_gbm"] = out[TARGET] - out["pred_gbm"]
    for name, frame in [("", out),
                        ("_metrics", pd.DataFrame(metrics)),
                        ("_importance", imp)]:
        dest = f"csv_exports/predictive_validation{name}_v{stamp}.csv"
        frame.to_csv(dest, index=False)
        print(f"saved -> {dest}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "csv_exports/modeling_dataset_v4_2026-07-24.csv")
