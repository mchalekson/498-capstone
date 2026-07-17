# Rigor classification — first pass (Section 4.1)

Implements the written report's Section 4.1 ("Academic Rigor Classification") exactly as
specified there: a transparent, weighted composite index across four named inputs, cut into
five ordinal tiers — **not** a supervised classifier trained against historical ground truth.
There is no "historical rigor labels from Bob" dependency here; that idea came from an earlier,
more tentative internal memo (`EDA_features_joined.md` §6) that predates the report's actual
plan and should be treated as superseded.

Code: `etl/build_rigor_classification.py`. Run against `modeling_dataset_v1_2026-07-17.csv`.

## Component mapping

The report names four inputs; here's what each maps to in the data we actually have:

| Report's named input | Columns used | Source |
|---|---|---|
| AP course counts/enrollment | `ap_tests_taken`, `number_of_ap_classes_offered_mid` | NU org export |
| IB course counts/enrollment | `ib_flag_candidate` | IB scraper, fuzzy-matched — **excluded, weight 0** |
| CRDC advanced-coursework indicators | `ap_participation`, `dual_enrollment_rate` | CRDC |
| Standardized test participation | `testtaker_rate`, `sat_participation_nu` | CRDC / NU |

Each is z-scored, sub-features within a component are averaged (only over whichever are
present for that school — no imputation), and the four component scores are combined with
per-row proportional weight reallocation over whichever components are actually available for
that school. A school with zero of the three active-weight components gets no score at all
(logged as `none`, not defaulted to a middle tier).

**IB is excluded from the default weighting**, per the report's own instruction: "IB participation
is not yet a usable rigor-classifier input" since none of the 1,354 fuzzy matches clear the
`auto_accept` tier (588 sit in `review`, 766 in `reject`). It's included only in the
`ib_included` sensitivity scenario below, to show what changes *if* it were trusted.

## Coverage

21,706 / 34,392 schools (63%) get a rigor score at all — 12,686 have none of the three
active-weight components and are correctly left unscored, not defaulted:

| # active components available | schools |
|---|---|
| 0 (unscored) | 12,686 |
| 1 | 2,853 |
| 2 | 10,843 |
| 3 (full coverage) | 8,010 |

Component availability: AP 31.3%, CRDC coursework 47.7%, test participation 62.2%.

## Nominal vs. effective weights

Required by the report because AP, CRDC coursework, and test participation are correlated —
the weight you *assign* isn't the share of variance a feature actually *contributes*. Computed
on the 8,010-school full-coverage subset (needed for the covariance terms):

| Component | Nominal weight | Effective weight |
|---|---|---|
| AP | 0.350 | 0.418 |
| CRDC coursework | 0.350 | 0.358 |
| Test participation | 0.300 | 0.224 |

AP pulls more effective weight than assigned; test participation pulls less — test
participation correlates more with the other two than they do with each other, so some of its
nominal weight is effectively "absorbed."

## Sensitivity analysis — alternate weighting schemes vs. the default ("designed")

| Scheme | Spearman rank corr. | Schools that changed tier | % changed |
|---|---|---|---|
| `equal` (1/3 each) | 0.998 | 1,228 | 5.7% |
| `ap_heavy` (0.50/0.25/0.25) | 0.988 | 3,020 | 13.9% |
| `test_heavy` (0.25/0.25/0.50) | 0.956 | 6,204 | 28.6% |
| `ib_included` (0.30/0.20 ib/0.25/0.25) | 0.973 | 9,178 | 42.3% |

Reasonably stable under modest weight perturbation (`equal`, `ap_heavy`), much less stable if
IB gets folded in at any real weight — one more reason to keep it excluded until match quality
improves.

## CRDC-available vs. CRDC-unavailable scenario

The report flags CRDC access as not guaranteed long-term (Office for Civil Rights transition —
see report Section 2's third finding) and explicitly asks for this comparison. Restricted to the
18,807 schools that actually have some CRDC signal today, recomputing tiers using only
NU-sourced signal instead (as if CRDC had never been available):

- 8,499 schools comparable both ways
- Spearman rank correlation: **0.76**
- **52.5% changed tier**

This is the most important number in this first pass: over half the CRDC-covered population
would land in a different tier if CRDC access were lost. The tier is not currently robust to that
dependency, and this needs to be surfaced to the client as-is, not smoothed over.

## Poverty / funding correlation with the rigor tier

Reported explicitly per the report's instruction, not folded in as an "independent enrichment
layer" — this is the number that would show whether the tier reproduces socioeconomic
ordering, the exact risk the composite-indicator literature review (Section 2.4) warns about:

- `spearman(tier, child_poverty_saipe)` = **-0.070**
- `spearman(tier, per_resident_child_funding_state_local)` = **0.025**
- `spearman(tier, per_pupil_state_local)` = **0.075**

All three are weak. Directionally sensible (more poverty → very slightly lower tier; more
funding → very slightly higher tier), but far too weak to say the tier is just re-deriving
socioeconomic status — which, per Section 2.4's own warning, would have been the concerning
result. Worth stating in the writeup as a positive finding, with the caveat that this is one
weighting scheme on one data snapshot, not a robustness proof.

## What this is not

- Not a final answer — tier cut-points are quintiles of the scored population, a transparent
  but arbitrary choice among several defensible ones. The report calls for a sensitivity
  analysis, not a single canonical cut-point.
- Not validated against any external rigor measure, because none exists in this project (see
  "historical labels" note above).
- Doesn't yet cover schools scored 0/3 components (37% of the HS universe) — those need a
  data-availability decision (e.g., report them as "insufficient data" rather than silently
  dropping them from any deliverable that uses tiers).

## Outputs

- `rigor_classification_<version>_<date>.csv` — every row from `modeling_dataset.csv` plus
  `rigor_score`, `rigor_tier_num`, `rigor_tier_label`, `rigor_n_components_used`,
  `rigor_components_available`, `rigor_weighting_scheme`.
- `rigor_sensitivity_<version>_<date>.csv` — the alternate-scheme comparison table above.
