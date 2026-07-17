"""
build_clustering.py -- feature engineering/PCA (report Section 4.3) and clustering
(Section 4.4) on top of modeling_dataset.csv / rigor_classification.csv.

Section 4.3 (Feature Engineering and Dimensionality Reduction): "apply principal component
analysis and related feature-selection techniques to the correlated rigor, funding, and
poverty features ... both to reduce dimensionality ahead of clustering and to make the
collinearity documented in Section 2.2 explicit and quantified rather than implicit. Any
engineered feature will be logged with the raw inputs it was derived from."

Section 4.4 (Pattern Recognition and Clustering): "apply K-means and hierarchical clustering
to group schools by location, academic profile, and funding characteristics, in order to
surface patterns among schools independent of the ordinal rigor tier ... the number of
clusters will be selected using the gap statistic (Tibshirani et al., 2001) and cross-checked
against silhouette scores, and any clustering result will be checked against the possibility
... that recovered clusters simply reproduce the same socioeconomic ordering that the rigor
tier already captures. If silhouette scores or gap-statistic results are weak, that will be
reported as a finding about the data rather than suppressed."

Design choice, and why it matters: clustering features here are the RAW inputs (AP/CRDC/test
participation components, grad rate, funding, poverty) -- NOT rigor_score itself. Including
the composite rigor score as a clustering input would make "do clusters reproduce the rigor
ordering" a tautology (of course they would, rigor would be a literal input). Clustering on
the same raw ingredients rigor is built from, then checking post-hoc whether clusters align
with the independently-computed rigor tier, is the non-circular version of the check the
report actually asks for.

Run:  python build_clustering.py rigor_classification_v1_2026-07-17.csv --k 4
"""
import argparse
import datetime as dt
import os
import sys

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score, adjusted_rand_score

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_rigor_classification import build_components, zscore  # noqa: E402

# location / academic-profile / funding-and-poverty -- the three axes the report names
LOCATION_COLS = ["latitude", "longitude"]
FUNDING_POVERTY_COLS = ["per_resident_child_funding_state_local", "child_poverty_saipe"]
ACADEMIC_EXTRA_COL = "grad_rate_2021"  # added alongside the rigor components (ap/crdc/test)


def build_feature_matrix(df):
    """
    Assemble the location / academic-profile / funding-poverty feature matrix, z-scored,
    complete-case only (no imputation, consistent with the rest of this pipeline -- see
    build_modeling_dataset.py / build_rigor_classification.py for the same stance).
    """
    comp = build_components(df)  # reuse ap / crdc_coursework / test_participation from rigor
    feats = pd.DataFrame(index=df.index)
    feats["latitude"] = zscore(df["latitude"])
    feats["longitude"] = zscore(df["longitude"])
    feats["ap"] = comp["ap"]
    feats["crdc_coursework"] = comp["crdc_coursework"]
    feats["test_participation"] = comp["test_participation"]
    feats["grad_rate"] = zscore(df[ACADEMIC_EXTRA_COL])
    feats["funding"] = zscore(df["per_resident_child_funding_state_local"])
    feats["poverty"] = zscore(df["child_poverty_saipe"])

    complete = feats.dropna()
    print(f"  [coverage] {len(complete):,}/{len(df):,} schools have complete data across all "
          f"{feats.shape[1]} clustering features (no imputation -- complete-case only)")
    for c in feats.columns:
        print(f"     {c:20} {100*feats[c].notna().mean():5.1f}% available")
    return complete


def quantify_collinearity(complete):
    """Section 4.3: make the rigor/funding/poverty collinearity explicit and quantified."""
    corr = complete.corr()
    print("\n[correlation matrix -- quantifying the collinearity Section 2.2 describes]")
    print(corr.round(2).to_string())
    return corr


def run_pca(complete):
    pca = PCA()
    pca.fit(complete.values)
    explained = pca.explained_variance_ratio_
    loadings = pd.DataFrame(pca.components_.T, index=complete.columns,
                             columns=[f"PC{i+1}" for i in range(len(explained))])
    print("\n[PCA] explained variance ratio by component:")
    for i, ev in enumerate(explained):
        print(f"   PC{i+1}: {ev*100:.1f}%  (cumulative {explained[:i+1].sum()*100:.1f}%)")
    print("\n[PCA] loadings (which raw features each component is derived from -- "
          "logged per Section 4.3's auditability requirement):")
    print(loadings.round(2).to_string())
    return pca, loadings


def gap_statistic(X, k_range, n_refs=10, random_state=42):
    """
    Tibshirani, Walther & Hastie (2001). Gap(k) = E*[log(W_k)] - log(W_k), where W_k is the
    real data's within-cluster dispersion for k clusters and E*[log(W_k)] is the average over
    n_refs uniform-random reference datasets spanning the same bounding box. Standard
    one-standard-error rule: pick the smallest k where Gap(k) >= Gap(k+1) - s_{k+1}.
    """
    rng = np.random.default_rng(random_state)
    mins, maxs = X.min(axis=0), X.max(axis=0)

    def log_wk(data, k):
        km = KMeans(n_clusters=k, n_init=10, random_state=random_state).fit(data)
        return np.log(km.inertia_)

    gaps, sks, real_logwk = [], [], []
    for k in k_range:
        wk_real = log_wk(X, k)
        real_logwk.append(wk_real)
        ref_logwk = []
        for _ in range(n_refs):
            ref = rng.uniform(mins, maxs, size=X.shape)
            ref_logwk.append(log_wk(ref, k))
        ref_logwk = np.array(ref_logwk)
        gap = ref_logwk.mean() - wk_real
        sk = ref_logwk.std() * np.sqrt(1 + 1 / n_refs)
        gaps.append(gap)
        sks.append(sk)

    gaps, sks = np.array(gaps), np.array(sks)
    chosen_k = k_range[-1]
    for i in range(len(k_range) - 1):
        if gaps[i] >= gaps[i + 1] - sks[i + 1]:
            chosen_k = k_range[i]
            break
    return pd.DataFrame({"k": list(k_range), "gap": gaps, "sk": sks, "log_wk": real_logwk}), chosen_k


def silhouette_sweep(X, k_range, random_state=42):
    scores = {}
    for k in k_range:
        km = KMeans(n_clusters=k, n_init=10, random_state=random_state).fit(X)
        scores[k] = silhouette_score(X, km.labels_)
    return scores


def check_reproduces_rigor_ordering(df, complete_idx, cluster_labels):
    """Report's explicit requirement: check whether clusters just reproduce the rigor tier's
    socioeconomic ordering rather than surfacing something new."""
    sub = df.loc[complete_idx].copy()
    sub["cluster"] = cluster_labels
    print("\n[cluster vs. rigor tier -- checking Section 2.4/4.4's 'just reproduces the "
          "ordering' concern]")
    tiered = sub.dropna(subset=["rigor_tier_num"])
    if len(tiered) > 1:
        by_cluster = tiered.groupby("cluster")["rigor_tier_num"].agg(["mean", "count"])
        print(by_cluster.round(2).to_string())
        overall_var = tiered["rigor_tier_num"].astype(float).var()
        between_var = tiered.groupby("cluster")["rigor_tier_num"].mean().var()
        print(f"   between-cluster variance in mean rigor tier: {between_var:.3f} "
              f"(overall tier variance: {overall_var:.3f}) -- "
              f"{'clusters DO track rigor tier' if between_var > 0.3*overall_var else 'clusters do NOT strongly track rigor tier'}")
    print("\n[cluster vs. funding/poverty -- same check, per Section 2.4]")
    for col in ["per_resident_child_funding_state_local", "child_poverty_saipe"]:
        by_cluster = sub.groupby("cluster")[col].mean()
        print(f"   mean {col} by cluster:\n{by_cluster.round(1).to_string()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="rigor_classification_v1_2026-07-17.csv")
    parser.add_argument("--version", default="v1")
    parser.add_argument("--outdir", default=".")
    parser.add_argument("--k-min", type=int, default=2)
    parser.add_argument("--k-max", type=int, default=8)
    args = parser.parse_args()

    df = pd.read_csv(args.path, low_memory=False)
    print(f"Loaded {args.path}: {len(df):,} rows")

    print("\n" + "=" * 72)
    print("SECTION 4.3 -- FEATURE ENGINEERING / DIMENSIONALITY REDUCTION")
    print("=" * 72)
    complete = build_feature_matrix(df)
    corr = quantify_collinearity(complete)
    pca, loadings = run_pca(complete)

    # reduce to components covering >=90% variance for the clustering step
    cum = np.cumsum(pca.explained_variance_ratio_)
    n_components = int(np.searchsorted(cum, 0.90) + 1)
    n_components = max(2, min(n_components, len(complete.columns)))
    X_pca = pca.transform(complete.values)[:, :n_components]
    print(f"\n[PCA] using first {n_components} components ({cum[n_components-1]*100:.1f}% "
          f"cumulative variance) for clustering below")

    print("\n" + "=" * 72)
    print("SECTION 4.4 -- PATTERN RECOGNITION AND CLUSTERING")
    print("=" * 72)
    k_range = list(range(args.k_min, args.k_max + 1))
    print(f"\n[gap statistic] evaluating k in {k_range} (Tibshirani et al. 2001, "
          f"one-standard-error rule)...")
    gap_df, gap_k = gap_statistic(X_pca, k_range)
    print(gap_df.round(3).to_string(index=False))
    print(f"   -> gap statistic selects k = {gap_k}")

    print(f"\n[silhouette scores] evaluating k in {k_range}...")
    sil_scores = silhouette_sweep(X_pca, k_range)
    for k, s in sil_scores.items():
        print(f"   k={k}: silhouette={s:.4f}")
    sil_k = max(sil_scores, key=sil_scores.get)
    print(f"   -> silhouette selects k = {sil_k}")

    if gap_k != sil_k:
        print(f"\n   !! gap statistic (k={gap_k}) and silhouette (k={sil_k}) disagree -- "
              f"reporting this honestly rather than picking whichever confirms a preferred "
              f"answer, per Section 4.4's own methodological commitment.")
    chosen_k = gap_k
    print(f"\n   Proceeding with k={chosen_k} (gap statistic, the report's stated primary "
          f"criterion; silhouette cross-checked above)")

    if max(sil_scores.values()) < 0.25:
        print(f"\n   !! FINDING: best silhouette score ({max(sil_scores.values()):.3f}) is weak "
              f"(<0.25) -- per Section 4.4, this is reported as a finding about the data's "
              f"cluster structure (or lack thereof), not suppressed or reframed.")

    kmeans = KMeans(n_clusters=chosen_k, n_init=10, random_state=42).fit(X_pca)
    hierarchical = AgglomerativeClustering(n_clusters=chosen_k).fit(X_pca)
    ari = adjusted_rand_score(kmeans.labels_, hierarchical.labels_)
    print(f"\n[K-means vs. hierarchical agreement] Adjusted Rand Index = {ari:.4f} "
          f"(1.0 = identical partitions, 0.0 = random agreement)")

    check_reproduces_rigor_ordering(df, complete.index, kmeans.labels_)

    out = df.copy()
    out["cluster_kmeans"] = pd.NA
    out["cluster_hierarchical"] = pd.NA
    out.loc[complete.index, "cluster_kmeans"] = kmeans.labels_
    out.loc[complete.index, "cluster_hierarchical"] = hierarchical.labels_
    for i in range(n_components):
        out[f"pca_component_{i+1}"] = np.nan
        out.loc[complete.index, f"pca_component_{i+1}"] = X_pca[:, i]
    out["clustering_features_used"] = "+".join(complete.columns)

    date_tag = dt.date.today().isoformat()
    out_path = os.path.join(args.outdir, f"clustering_{args.version}_{date_tag}.csv")
    out.to_csv(out_path, index=False)
    print(f"\nWrote {out_path} ({out.shape[0]:,} rows x {out.shape[1]} cols)")

    loadings_path = os.path.join(args.outdir, f"pca_loadings_{args.version}_{date_tag}.csv")
    loadings.to_csv(loadings_path)
    print(f"Wrote {loadings_path}")

    gap_path = os.path.join(args.outdir, f"gap_statistic_{args.version}_{date_tag}.csv")
    gap_df.to_csv(gap_path, index=False)
    print(f"Wrote {gap_path}")
