# Rigor index — v4 revisions (scenarios A + B), 2026-07-24

> **Status: ADOPTED (2026-07-26).** A+B is now the shipped default — `COMPONENT_SPECS["v4"]`
> in `etl/build_rigor_classification.py`, with the two derived features
> (`ap_qualifying_density`, `ib_intensity_v2`) built in `etl/build_modeling_dataset.py`.
> The whole chain was re-run and reproduces the committed v4 outputs exactly
> (max |Δrigor_score| = 3.6e-15). `docs/RIGOR_CLASSIFICATION.md` now carries the v4 numbers,
> and `BENCHMARKING.md` / `RIGOR_ANALYSIS.md` were regenerated on v4. Pass `--spec v3` to
> reproduce the prior index. This file is retained as the scenario audit trail.
>
> Adoption checklist (below) — (1) sensitivity + effective weights rerun: **done**;
> (2) refit migration reported: **done** (frozen-cut-point decomposition remains scenario-A
> only); (3) SD≈1.2 and IB asymmetry documented: **done**, in `RIGOR_CLASSIFICATION.md`
> and the `build_modeling_dataset.py` docstrings.

Two candidate changes to the shipped v3 "designed" index, run as scenarios against
`modeling_dataset_v3_2026-07-24.csv` without touching the default. Outputs:
`csv_exports/rigor_scenarioA_ibv2_2026-07-24.csv`, `csv_exports/rigor_scenarioB_qualdensity_2026-07-24.csv`.

## Scenario A — IB folded into CRDC coursework (uses the rescued `ib_flag_v2`)

IB enters as an intensity sub-feature (`crdc_ib_enrollment / enrollment_9_12`, fallback to the
adjudicated binary flag) inside the `crdc_coursework` component. No weight changes. Versus the
default: Spearman 0.980; with frozen tier cut-points, 11.4% migrate — IB-positive schools 235 up
/ 6 down (the intended effect), non-IB movers are boundary cases from the confirmed-zero-vs-
unknown asymmetry (documented). 94 previously unscorable schools gain a score. See
`docs/IB_RESCUE.md` for the flag's provenance.

## Scenario B — AP performance re-specified as qualifying density

Replaces the mean AP exam score with **qualifying density**: expected qualifying exams (score
≥ 3) per student, computed as `ap_tests_taken × P(score ≥ 3)`, where P is derived from the
school's mean score under a normal approximation (within-school SD ≈ 1.2; a documented
approximation — the College Board does not publish school score distributions).

Why: a mean score rewards gatekeeping — a school that lets only its strongest students sit
exams posts a high mean; an open-access school is punished for breadth. Density fuses
opportunity × performance and is the College Board's own equity-metric logic.

Empirical checks (all favorable):

| Metric | Default (mean score) | B (qualifying density) |
|---|---|---|
| Rigor ~ county poverty (Spearman) | −0.146 | **−0.124** (less SES-confounded) |
| Performance metric ~ take rate | −0.144 (punishes open access) | **−0.091** (37% less) |
| Spearman vs default score | — | 0.987 |
| Tier migration (refit breaks) | — | 8.4% |

## Combined (A+B) — the v4 candidate

Both changes together: Spearman 0.968 vs default; 23.5% tier migration under refit natural
breaks (much of it cut-point instability — see the frozen-cut-point decomposition in scenario A);
rigor~poverty improves to −0.118; effective weights remain performance-led (AP performance
0.310, test performance 0.230); scored population grows to 21,951. New Trier remains Very
Demanding under all three variants.

## Recommendation

Adopt A+B as v4 after team review: it uses the verified IB flag, replaces a
gatekeeping-sensitive metric with an equity-consistent one, reduces SES confounding, and holds
the golden-school checks. Required before shipping: (1) rerun the full sensitivity table and
nominal-vs-effective weights in `build_rigor_classification.py` with the new component
definitions; (2) present both refit and frozen-cut-point migration numbers (the natural-breaks
method is sensitive to score-distribution shifts — a finding to report in its own right);
(3) document the SD≈1.2 approximation and the confirmed-zero-vs-unknown IB asymmetry in the
methods subsection.
