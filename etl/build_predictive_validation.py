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


def main(path):
    df = pd.read_csv(path, low_memory=False)
    df = df[df["sector"] == "public"].copy()
    for c in OPPORTUNITY + SES + [TARGET]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # complete cases across target + both predictor blocks (same rows for all nested models)
    cc = df.dropna(subset=[TARGET] + OPPORTUNITY + SES)
    print(f"public schools: {len(df):,} | complete-case for validation: {len(cc):,}")

    y = cc[TARGET]
    idx_tr, idx_te = train_test_split(cc.index, test_size=0.2, random_state=SEED)
    results = {}
    results["ses_only"], _, _ = fit_eval(cc.loc[idx_tr, SES], cc.loc[idx_te, SES],
                                         y.loc[idx_tr], y.loc[idx_te], "SES only")
    results["opportunity_only"], _, _ = fit_eval(cc.loc[idx_tr, OPPORTUNITY], cc.loc[idx_te, OPPORTUNITY],
                                                 y.loc[idx_tr], y.loc[idx_te], "Opportunity only")
    both = SES + OPPORTUNITY
    results["ses_plus_opportunity"], lr_full, hgb_full = fit_eval(
        cc.loc[idx_tr, both], cc.loc[idx_te, both], y.loc[idx_tr], y.loc[idx_te], "SES + Opportunity")

    inc_lin = results["ses_plus_opportunity"]["linear"]["r2"] - results["ses_only"]["linear"]["r2"]
    inc_gbm = results["ses_plus_opportunity"]["gbm"]["r2"] - results["ses_only"]["gbm"]["r2"]
    print(f"\nINCREMENTAL R2 of opportunity over SES:  linear +{inc_lin:.3f} | gbm +{inc_gbm:.3f}")

    print("\npermutation importance (gbm, SES+Opportunity, test set):")
    pi = permutation_importance(hgb_full, cc.loc[idx_te, both], y.loc[idx_te],
                                n_repeats=10, random_state=SEED)
    imp = pd.Series(pi.importances_mean, index=both).sort_values(ascending=False)
    print(imp.round(3).to_string())

    print("\nstandardized linear coefficients (SES+Opportunity):")
    Xz = (cc[both] - cc[both].mean()) / cc[both].std()
    lrz = LinearRegression().fit(Xz.loc[idx_tr], y.loc[idx_tr])
    print(pd.Series(lrz.coef_, index=both).round(2).sort_values().to_string())

    # sensitivity: HGB on all public rows with a target (native NaN handling)
    allr = df.dropna(subset=[TARGET])
    Xtr, Xte, ytr, yte = train_test_split(allr[both], allr[TARGET], test_size=0.2, random_state=SEED)
    hgb_all = HistGradientBoostingRegressor(random_state=SEED).fit(Xtr, ytr)
    print(f"\nrobustness (all {len(allr):,} public rows w/ target, HGB w/ NaN): "
          f"R2={r2_score(yte, hgb_all.predict(Xte)):.3f}")

    stamp = path.split("_v")[-1].replace(".csv", "")
    out = cc.loc[idx_te, ["ceeb", "school_name", "state", TARGET]].copy()
    out["pred_linear"] = lr_full.predict(cc.loc[idx_te, both])
    out["pred_gbm"] = hgb_full.predict(cc.loc[idx_te, both])
    out["residual_gbm"] = out[TARGET] - out["pred_gbm"]
    dest = f"csv_exports/predictive_validation_v{stamp}.csv"
    out.to_csv(dest, index=False)
    print(f"\nsaved test-set predictions -> {dest}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "csv_exports/modeling_dataset_v3_2026-07-24.csv")
