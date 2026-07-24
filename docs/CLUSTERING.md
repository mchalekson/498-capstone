# Feature engineering (PCA) + clustering — Sections 4.3–4.4

Code: `etl/build_clustering.py`. Run against `rigor_classification_v3_2026-07-24.csv`.

## Design choice: clustering does NOT use `rigor_score` as an input

The report's concern (Sections 2.4, 4.4) is whether recovered clusters just reproduce the
rigor tier's ordering. If `rigor_score` were itself a clustering feature, that check would be
circular. Instead, clustering runs on the same **raw** ingredients rigor is built from
(AP/CRDC/test-participation components, grad rate) plus location and funding/poverty, and the
alignment with the independently-computed rigor tier is checked *after the fact*.

## Feature set (location / academic profile / funding, per Section 4.4)

| Axis | Features |
|---|---|
| Location | **`us_region` one-hots** (Midwest / Northeast / South / West) — *changed Wk5: raw `latitude`/`longitude` removed per client feedback that coordinates are meaningless in a Euclidean distance; region is the interpretable geographic signal* |
| Academic profile | `ap_opportunity`, `crdc_coursework`, `test_participation` (same z-scored components as the rigor classifier), `grad_rate_2021` |
| Funding / poverty | `per_resident_child_funding_state_local`, `child_poverty_saipe` |

`region_Illinois` is dropped automatically: no IL school clears the complete-case filter, so
its one-hot is constant-zero (no signal). The two new **performance** components
(`ap_performance`, `test_performance`, ~31% coverage) are deliberately **excluded** from
clustering — forcing them into the complete-case intersection would decimate N.

## Coverage — the real limitation of this pass

**Only 5,801 of 34,392 schools (16.9%) have complete data across all clustering features.** No
imputation, consistent with the rest of the pipeline — but the clustering result describes a
specific, non-random subset (schools with region, funding, *and* some academic signal at
once), not the full HS universe. State this alongside any clustering result in the writeup.

## Collinearity (Section 4.3's ask — "quantified rather than implicit")

Notable pairs from the correlation matrix (script output):
- `funding` correlates **0.68** with `region_Northeast` and **−0.41** with `region_South` —
  funding varies strongly by region, as expected.
- `poverty` anti-correlates with funding (−0.29) and with the academic components (−0.08 to
  −0.20) — the expected direction, consistent with (not proof of) the socioeconomic-ordering
  concern.
- `ap_opportunity` and `crdc_coursework` correlate 0.35 — both AP-adjacent, different sources.

## PCA

10 raw features (after dropping constant `region_Illinois`) need **6 components for 90%+
cumulative variance** (91.8% at 6) — a modest reduction. PC1 (33.6%) loads on `funding`
(0.77) against `poverty` (−0.47), with `region_Northeast` (0.24) positive and `region_South`
(−0.21) negative — a **"regional wealth"** axis. PC2 (17.6%) loads on `test_participation`
(0.63), `crdc_coursework` (0.57), `ap_opportunity` (0.37) — an **"academic intensity"** axis,
separate from PC1. PC3 (15.7%) is dominated by `poverty` (0.84) and `funding` (0.44). Full
loadings: `pca_loadings_v3_2026-07-24.csv`.

## Cluster count: gap statistic vs. silhouette disagree

Gap statistic (one-standard-error rule, Tibshirani et al. 2001) selects **k=4**. Silhouette
peaks at **k=2** (0.270) and declines. They disagree — reported, not resolved by picking the
convenient one. Proceeded with k=4 (report's stated primary criterion; silhouette as cross-check).

**Best silhouette anywhere in k=2..8 is 0.270** — only just above the conventional 0.25
threshold, and the k=4 value (0.187) is below it. Per the report's instruction, this is a
**finding about the data**: the 5,801-school complete-case population has weak natural cluster
separation on these features; plausible groups blur rather than forming tight regions.

## K-means vs. hierarchical agreement

Adjusted Rand Index between the two methods' k=4 partitions: **0.39** (1.0 = identical, 0.0 =
chance). Moderate — broadly similar but not matching structure, consistent with the weak
silhouette (soft, overlapping clusters are where clustering algorithms diverge most).

## Does clustering reproduce the rigor tier's ordering?

Partially, not fully:

| Cluster | Mean rigor tier (0–4) | n | Mean funding | Mean poverty % |
|---|---|---|---|---|
| 0 | 1.31 | 2,050 | $14,854 | 11.1% |
| 1 | 1.05 | 1,521 | $12,881 | 21.2% |
| 2 | 2.04 | 981 | **$27,487** | 10.6% |
| 3 | 2.18 | 1,249 | $13,898 | 12.0% |

Between-cluster variance in mean rigor tier is 0.305 against overall 0.676 — roughly **45% of
rigor-tier variation sits between clusters**. Real alignment, not total: clusters 2 and 3 both
have high mean rigor despite very different funding ($27k vs. $14k), and cluster 1 has the
lowest rigor tier *and* the highest poverty (21.2%) — the exact pattern the composite-indicator
literature (Section 2.4) warns to watch. Cluster 2 is a distinct "well-funded, high-rigor"
group worth a closer look before generalizing.

## What this is not

- Not based on the full HS universe — 16.9% complete-case coverage is a real constraint.
- Not evidence of strong, well-separated school "types" — the weak silhouette says the opposite.
- Not validated against anything external, same limitation as the rigor tier itself.

## Outputs

- `clustering_v3_2026-07-24.csv` — rigor-classification rows plus `cluster_kmeans`,
  `cluster_hierarchical`, `pca_component_1..6`, `clustering_features_used`.
- `pca_loadings_v3_2026-07-24.csv` — full PCA loadings table.
- `gap_statistic_v3_2026-07-24.csv` — gap statistic values across k=2..8.
