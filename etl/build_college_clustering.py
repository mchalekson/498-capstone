"""
build_college_clustering.py -- cluster the CEEB-mapped colleges (secondary goal:
"group similar institutions by location, academic and financial characteristics,
student funding; detect patterns").

Input: csv_exports/ope_ceeb_scorecard_merged_clean_<date>.csv -- the OPE<->CEEB
junction joined to College Scorecard / IPEDS (4,004 CEEB college codes), ENRICHED
here with IPEDS HD2023 for the geography the clean merge left out (locale/urbanicity,
lat-long, Carnegie level). This is COLLEGE-level, distinct from build_clustering.py.

Approach mirrors build_clustering.py (z-score -> PCA -> KMeans, complete-case, no
silent imputation), with dataset-specific decisions this data forces:

  1. Universe. ~30% of rows have no IPEDS match (hospitals/institutes that hold a
     CEEB, closed / non-Title-IV schools). They carry no features, so they are
     excluded; only degree-granting institutions (predominant degree =
     associate/bachelor's/graduate) are clustered.

  2. Feature set. Selectivity (SAT, admission rate) is only ~40-60% covered because
     open-admission and 2-year schools are exempt from those IPEDS components, so
     they are reported as cluster *profile overlays*, not clustering inputs. The
     coverage-robust core is size, sector, price, Pell share, urbanicity and region.

  3. Two cluster columns. Silhouette favours k=2 -- the public-2yr vs private-4yr
     divide dominates -- so a `cluster` (silhouette-best, the natural structure) and
     a `cluster_fine` (fixed k=6, operational segments) are both emitted.

Run:  python build_college_clustering.py \
        ../csv_exports/ope_ceeb_scorecard_merged_clean_2026-08-02.csv --outdir ../csv_exports
"""
import argparse
import datetime as dt
import os

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score

RS = 42
K_FINE = 6

CENSUS_REGION = {
    **dict.fromkeys(["CT", "ME", "MA", "NH", "RI", "VT", "NJ", "NY", "PA"], "Northeast"),
    **dict.fromkeys(["IL", "IN", "MI", "OH", "WI", "IA", "KS", "MN", "MO", "NE", "ND", "SD"], "Midwest"),
    **dict.fromkeys(["DE", "FL", "GA", "MD", "NC", "SC", "VA", "DC", "WV", "AL", "KY", "MS",
                     "TN", "AR", "LA", "OK", "TX"], "South"),
    **dict.fromkeys(["AZ", "CO", "ID", "MT", "NV", "NM", "UT", "WY", "AK", "CA", "HI", "OR", "WA"], "West"),
}
CONTROL_LABEL = {1: "public", 2: "private nonprofit", 3: "private for-profit"}
PREDDEG_LABEL = {0: "non-degree", 1: "certificate", 2: "associate", 3: "bachelor's", 4: "graduate"}
ICLEVEL_LABEL = {1: "4-year", 2: "2-year", 3: "<2-year"}
# IPEDS LOCALE first digit: 1 City, 2 Suburb, 3 Town, 4 Rural. Ordinal urbanicity 4..1.
LOCALE_URBAN = {1: 4, 2: 3, 3: 2, 4: 1}
LOCALE_LABEL = {4: "City", 3: "Suburb", 2: "Town", 1: "Rural"}

DIMENSIONS = {
    "location": ["state", "region", "urbanicity", "latitude"],
    "academic": ["sc_adm_rate", "sc_sat_avg", "sc_completion_150_4yr", "sc_retention_ft4", "sc_preddeg"],
    "financial": ["sc_tuition_in", "sc_tuition_out", "net_price"],
    "student_funding": ["sc_pct_pell"],
    "size_sector": ["sc_ugds", "sc_control", "iclevel"],
}


def load_hd(path):
    """IPEDS HD2023 directory -> the geography the clean merge lacks. The first column
    carries a UTF-8 BOM that turns to mojibake under latin-1, so strip every non-
    alphanumeric from the headers before selecting."""
    import re
    hd = pd.read_csv(path, encoding="latin-1", dtype=str)
    hd.columns = [re.sub(r"[^A-Za-z0-9]", "", c).upper() for c in hd.columns]
    hd["unitid"] = pd.to_numeric(hd["UNITID"], errors="coerce").astype("Int64")
    loc1 = pd.to_numeric(hd["LOCALE"], errors="coerce") // 10
    hd["urbanicity"] = loc1.map(LOCALE_URBAN)
    hd["latitude"] = pd.to_numeric(hd["LATITUDE"], errors="coerce")
    hd["longitude"] = pd.to_numeric(hd["LONGITUD"], errors="coerce")
    hd["iclevel"] = pd.to_numeric(hd["ICLEVEL"], errors="coerce")
    hd["carnegie_basic"] = pd.to_numeric(hd["C21BASIC"], errors="coerce")
    return hd[["unitid", "urbanicity", "latitude", "longitude", "iclevel", "carnegie_basic"]]


def prep(df):
    df = df.copy()
    df["net_price"] = df["sc_netprice_pub"].fillna(df["sc_netprice_priv"])
    df["region"] = df["state"].map(CENSUS_REGION).fillna("Other/Territory")
    df["log_ugds"] = np.log1p(pd.to_numeric(df["sc_ugds"], errors="coerce"))
    df["is_public"] = (pd.to_numeric(df["sc_control"], errors="coerce") == 1).astype(float)
    return df


def coverage_report(universe):
    print(f"\n[coverage] by clustering dimension (share non-null over the "
          f"{len(universe):,}-college degree-granting universe):")
    rows = [{"dimension": dim, "feature": c, "pct_covered": round(100 * universe[c].notna().mean(), 1)}
            for dim, cols in DIMENSIONS.items() for c in cols if c in universe.columns]
    cov = pd.DataFrame(rows)
    print(cov.to_string(index=False))
    return cov


def profile(clustered, col):
    rows = []
    for cid, g in clustered.groupby(col):
        ctrl = pd.to_numeric(g["sc_control"], errors="coerce").map(CONTROL_LABEL).mode()
        deg = pd.to_numeric(g["sc_preddeg"], errors="coerce").map(PREDDEG_LABEL).mode()
        urb = pd.to_numeric(g["urbanicity"], errors="coerce").round().map(LOCALE_LABEL).mode()
        rows.append({
            "cluster": int(cid), "size": len(g),
            "top_control": ctrl.iloc[0] if len(ctrl) else "",
            "top_degree": deg.iloc[0] if len(deg) else "",
            "top_urbanicity": urb.iloc[0] if len(urb) else "",
            "top_region": g["region"].mode().iloc[0] if g["region"].notna().any() else "",
            "med_ugds": int(pd.to_numeric(g["sc_ugds"], errors="coerce").median()),
            "med_net_price": round(float(pd.to_numeric(g["net_price"], errors="coerce").median()), 0),
            "mean_pct_pell": round(float(pd.to_numeric(g["sc_pct_pell"], errors="coerce").mean()), 3),
            "mean_adm_rate": round(float(pd.to_numeric(g["sc_adm_rate"], errors="coerce").mean()), 3),
            "mean_sat_avg": round(float(pd.to_numeric(g["sc_sat_avg"], errors="coerce").mean()), 0),
            "mean_completion": round(float(pd.to_numeric(g["sc_completion_150_4yr"], errors="coerce").mean()), 3),
        })
    return pd.DataFrame(rows).sort_values("cluster")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--hd", default=os.path.join(os.path.dirname(__file__), "..", "data", "IPEDS", "HD2023.csv"))
    ap.add_argument("--outdir", default="../csv_exports")
    ap.add_argument("--k-min", type=int, default=2)
    ap.add_argument("--k-max", type=int, default=10)
    args = ap.parse_args()

    raw = pd.read_csv(args.path, dtype={"ceeb": str, "opeid": str, "unitid": str}, low_memory=False)
    print(f"Loaded {os.path.basename(args.path)}: {len(raw):,} CEEB college rows")
    df = prep(raw)

    # --- enrich with HD2023 geography ------------------------------------------
    df["unitid_i"] = pd.to_numeric(df["unitid"], errors="coerce").astype("Int64")
    hd = load_hd(args.hd)
    df = df.merge(hd, left_on="unitid_i", right_on="unitid", how="left", suffixes=("", "_hd"))
    print(f"[enrich] HD2023 joined on unitid: urbanicity {df['urbanicity'].notna().mean()*100:.0f}%, "
          f"lat/long {df['latitude'].notna().mean()*100:.0f}% of all rows")

    # --- universe ---------------------------------------------------------------
    matched = df["unitid_i"].notna()
    preddeg = pd.to_numeric(df["sc_preddeg"], errors="coerce")
    degree_granting = preddeg.isin([2, 3, 4])
    uni = df[matched & degree_granting & df["sc_ugds"].notna()].copy()
    print(f"[universe] {int(matched.sum()):,} IPEDS-matched · "
          f"{int((matched & ~degree_granting).sum()):,} matched-but-non-degree dropped · "
          f"{int((~matched).sum()):,} unmatched dropped -> {len(uni):,} degree-granting colleges")

    cov = coverage_report(uni)

    # --- clustering feature matrix (coverage-robust core, now incl. urbanicity) -
    CORE = ["log_ugds", "net_price", "sc_pct_pell", "sc_tuition_in", "is_public", "urbanicity"]
    X = uni[CORE].apply(pd.to_numeric, errors="coerce")
    region_dummies = pd.get_dummies(uni["region"], prefix="region").astype(float)
    X = pd.concat([X, region_dummies], axis=1)

    complete = X[CORE].notna().all(axis=1)
    Xc = X[complete].copy()
    for c in CORE:
        Xc[c] = (Xc[c] - Xc[c].mean()) / Xc[c].std(ddof=0)
    print(f"\n[features] clustering on {CORE} + region dummies · "
          f"complete-case {int(complete.sum()):,}/{len(uni):,} "
          f"({100*complete.sum()/len(uni):.0f}% of degree-granting universe)")

    pca = PCA(n_components=0.90, random_state=RS).fit(Xc.values)
    Z = pca.transform(Xc.values)
    print(f"[pca] {Z.shape[1]} components retain 90% variance")

    sweep = [(k, silhouette_score(Z, KMeans(n_clusters=k, n_init=10, random_state=RS).fit_predict(Z)))
             for k in range(args.k_min, args.k_max + 1)]
    best_k = max(sweep, key=lambda t: t[1])[0]
    print("[k sweep] silhouette: " + ", ".join(f"{k}:{s:.3f}" for k, s in sweep))
    print(f"[k sweep] silhouette selects k={best_k} (natural split); also emitting k={K_FINE} (fine segments)")

    uni.loc[complete, "cluster"] = KMeans(n_clusters=best_k, n_init=10, random_state=RS).fit_predict(Z)
    uni.loc[complete, "cluster_fine"] = KMeans(n_clusters=K_FINE, n_init=10, random_state=RS).fit_predict(Z)
    for i in range(min(Z.shape[1], 3)):
        uni.loc[complete, f"pca_{i+1}"] = Z[:, i]

    clustered = uni[uni["cluster"].notna()].copy()
    prof_main = profile(clustered.assign(cluster=clustered["cluster"].astype(int)), "cluster")
    prof_fine = profile(clustered.assign(cluster_fine=clustered["cluster_fine"].astype(int)), "cluster_fine")
    print("\n[natural clusters]"); print(prof_main.to_string(index=False))
    print(f"\n[fine segments · k={K_FINE}]"); print(prof_fine.to_string(index=False))

    # --- write ------------------------------------------------------------------
    date_tag = dt.date.today().isoformat()
    keep = ["ceeb", "org_name", "sc_instnm", "state", "region", "urbanicity", "latitude", "longitude",
            "sc_control", "sc_preddeg", "iclevel", "carnegie_basic", "sc_ugds", "sc_tuition_in",
            "net_price", "sc_pct_pell", "sc_adm_rate", "sc_sat_avg", "sc_completion_150_4yr",
            "cluster", "cluster_fine", "pca_1", "pca_2"]
    out_main = os.path.join(args.outdir, f"college_clustering_{date_tag}.csv")
    uni[[c for c in keep if c in uni.columns]].to_csv(out_main, index=False)
    prof_main.to_csv(os.path.join(args.outdir, f"college_cluster_profiles_{date_tag}.csv"), index=False)
    prof_fine.to_csv(os.path.join(args.outdir, f"college_cluster_profiles_fine_{date_tag}.csv"), index=False)
    cov.to_csv(os.path.join(args.outdir, f"college_clustering_coverage_{date_tag}.csv"), index=False)
    print(f"\nWrote {out_main} ({len(uni):,} colleges) + profiles + coverage")


if __name__ == "__main__":
    main()
