# Feature engineering (PCA) + clustering — first pass (Sections 4.3-4.4)

Code: `etl/build_clustering.py`. Run against `rigor_classification_v1_2026-07-17.csv`.

## Design choice: clustering does NOT use `rigor_score` as an input

The report's concern (Sections 2.4, 4.4) is whether recovered clusters just reproduce the
rigor tier's ordering. If `rigor_score` were itself a clustering feature, that check would be
circular — of course clusters would align with rigor, it would be a literal input. Instead,
clustering runs on the same **raw** ingredients rigor is built from (AP/CRDC/test-participation
components, grad rate) plus location (lat/long) and funding/poverty, and the alignment with
the independently-computed rigor tier is checked *after the fact*. That's the non-circular
version of the report's own instruction.

## Feature set (location / academic profile / funding, per Section 4.4)

| Axis | Features |
|---|---|
| Location | `latitude`, `longitude` (NU-sourced) |
| Academic profile | `ap`, `crdc_coursework`, `test_participation` (same z-scored components as the rigor classifier), `grad_rate_2021` |
| Funding / poverty | `per_resident_child_funding_state_local`, `child_poverty_saipe` |

## Coverage — the real limitation of this pass

**Only 5,797 of 34,392 schools (16.9%) have complete data across all 8 features.** No
imputation, consistent with the rest of this pipeline — but this means the clustering result
below describes a specific, non-random subset (schools with lat/long from NU, funding, *and*
some academic signal all at once), not the full HS universe. This should be stated plainly
alongside any clustering result used in the writeup, not glossed over.

## Collinearity (Section 4.3's explicit ask — "quantified rather than implicit")

Full correlation matrix in the script output. Notable pairs:
- `funding` correlates 0.35-0.37 with `latitude`/`longitude` — funding varies meaningfully by
  region, as expected.
- `poverty` anti-correlates with almost everything academic and with funding (-0.17 to -0.29)
  — the expected direction, consistent with (not proof of) the socioeconomic-ordering concern.
- `ap` and `crdc_coursework` correlate 0.39 — expected, they're both AP-adjacent measures from
  different sources.

## PCA

8 raw features need **6 components for 90%+ cumulative variance** (92.0% at 6). That's a
modest reduction, not a dramatic one — these 8 features are correlated but not so collinear
that a small number of components captures everything. PC1 (31.2% of variance) loads heavily
on `funding` (0.66) and `latitude` (0.47) with `poverty` pulling the opposite direction
(-0.45) — a "regional wealth" axis. PC2 (20.6%) loads on `ap` (0.68) and `crdc_coursework`
(0.37) — an "AP/coursework intensity" axis, separate from PC1. Full loadings table:
`pca_loadings_v1_2026-07-17.csv`.

## Cluster count: gap statistic vs. silhouette disagree

Per Tibshirani et al. (2001), the gap statistic (with the standard one-standard-error rule)
selects **k=4**. Silhouette scores peak at **k=2** (0.205) and decline from there. The report
asks these two criteria be cross-checked against each other, not that one be picked to match
the other — **they disagree here, and that's reported rather than resolved by picking
whichever looks better.** Proceeded with k=4 (the report names the gap statistic as the
primary criterion, silhouette as the cross-check).

**The best silhouette score anywhere in k=2..8 is 0.205 — below the conventional 0.25
threshold for meaningful cluster structure.** Per the report's own instruction ("if silhouette
scores or gap-statistic results are weak, that will be reported as a finding about the data
rather than suppressed or reframed as a modeling failure"): this is a finding about the
5,797-school complete-case population, not a clustering-method failure. The data doesn't have
strong natural cluster separation on these 8 features — plausible groups blur into each other
rather than forming tight, well-separated regions.

## K-means vs. hierarchical agreement

Adjusted Rand Index between the two methods' k=4 partitions: **0.32** (1.0 = identical, 0.0 =
random chance agreement). Moderate, not strong — the two methods find broadly similar but not
matching structure, consistent with the weak silhouette finding above (soft, overlapping
clusters are exactly where different clustering algorithms diverge most).

## Does clustering reproduce the rigor tier's ordering?

Partially, not fully:

| Cluster | Mean rigor tier (0-4 scale) | n | Mean funding | Mean poverty % |
|---|---|---|---|---|
| 0 | 3.03 | 1,175 | $12,344 | 14.6% |
| 1 | 1.81 | 1,938 | $15,201 | 10.2% |
| 2 | 1.26 | 1,570 | $13,400 | 20.4% |
| 3 | 2.82 | 1,114 | **$26,293** | 10.2% |

Between-cluster variance in mean rigor tier is 0.705 against an overall variance of 1.605 —
roughly **44% of rigor-tier variation sits between clusters** rather than within them. That's
real alignment, not nothing, but far from total: clusters 0 and 3 both have high mean rigor
tiers despite very different funding profiles ($12k vs. $26k), and cluster 2 has the lowest
rigor tier *and* the highest poverty rate, which is the exact pattern the composite-indicator
literature (Section 2.4) warns to watch for. Cluster 3 in particular looks like a distinct
"well-funded, high-rigor" outlier group worth a closer look before generalizing from it.

## What this is not

- Not based on the full HS universe — 16.9% complete-case coverage is a real constraint on how
  far these findings generalize.
- Not evidence of strong, well-separated school "types" — the weak silhouette score says the
  opposite, and that's the honest reading, not a caveat to bury.
- Not validated against anything external, same limitation as the rigor tier itself.

## Outputs

- `clustering_<version>_<date>.csv` — every row from the rigor classification output plus
  `cluster_kmeans`, `cluster_hierarchical`, `pca_component_1..6`, `clustering_features_used`.
- `pca_loadings_<version>_<date>.csv` — full PCA loadings table.
- `gap_statistic_<version>_<date>.csv` — gap statistic values across k=2..8.
