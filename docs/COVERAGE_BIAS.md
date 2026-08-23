# Coverage bias — who has data, and what the index does to schools that don't

**Status: the second half of this document is a blocking finding for model sign-off.**

Code: `etl/build_visit_bias.py`. Run against `rigor_classification_v4_2026-07-24.csv`.
Outputs `csv_exports/visit_bias_v4_<date>.csv` and `docs/fig/visit_bias.png`.

There is one causal chain here, in two parts:

1. **Who has data is determined by NU's recruiting footprint** — the NU-sourced fields refresh
   only for schools with application activity, so they populate at ~89% where NU has visited and
   ~21% where it has not.
2. **The index systematically mis-scores the schools left thin by (1)** — proportional weight
   reallocation gives a school scored on one component the full variance of that one component,
   so thin-data schools are ~10x more likely to reach the top tier than fully-covered ones. 74%
   of the current "Most Demanding" tier is scored on 2 or fewer of 5 components.

Part 1 is a caveat to report. **Part 2 is a defect to fix before the tiers are signed off.**

---

## Part 1 — the refresh gate is visible in our data

The Wk6 client discussion established the mechanism: the NU school fields refresh weekly, but
only for schools with an application in flight. Schools with no application activity are never
touched.

The org export carries exactly one date column — `Last Visit`, when an NU representative last
visited the school. It is a direct observable proxy for recruiting engagement, and it separates
the population cleanly. Of 44,899 org records, **3,630 (8.1%) have ever been visited.**

| NU-sourced field | Visited | Never visited | Gap |
|---|---|---|---|
| `sat_score_nu` | 90.9% | 23.1% | 67.8 pp |
| `ap_score_nu` | 88.8% | 21.4% | 67.4 pp |
| `ap_tests_taken` | 88.8% | 21.4% | 67.4 pp |
| `sat_participation_nu` | 88.8% | 20.8% | 68.0 pp |
| `ap_pct_students_nu` | 87.7% | 21.1% | 66.6 pp |

A ~4x gap, consistent across every gated field. This confirms the client's description from our
side of the data, and it is not a small technicality: `ap_qualifying_density` and `sat_score_nu`
are the two components carrying the **highest effective weight** in the shipped v4 index (0.310
and 0.230 — together ~54% of the composite's variance). The index's dominant signal is
available preferentially where NU already recruits.

`Last Visit` also reads as a genuine travel calendar — Sept/Oct clustering, a collapse to 6
visits in 2020, and a rebuild through 2023 (328), 2024 (602), 2025 (1,011).

### What it does to scorability and to the tier

| | Visited (n=3,196) | Never visited (n=31,196) |
|---|---|---|
| Gets a rigor score at all | **98.5%** | **60.3%** |
| Mean `rigor_score` (of those scored) | +0.445 | −0.118 |
| Median | +0.402 | −0.170 |

Share of each tier NU has ever visited: 2.8% → 7.6% → 21.1% → 39.3% across the bottom four
tiers. (The top tier breaks the pattern at 20.0% — that anomaly is Part 2.)

### Selection or measurement? Mostly selection.

Two channels are confounded, and they have different implications:

- **Selection** — NU visits schools it already believes are strong, so they would score higher
  even with perfect data everywhere. Real signal, not an artifact.
- **Measurement** — visiting populates the fields that make a school scorable on the performance
  components at all. This is the channel a dummy-record push would fix.

Holding data availability constant (restricting to schools where *every* component is present):

| | Gap in mean `rigor_score` |
|---|---|
| All scored schools | 0.564 |
| Full-coverage subset only (n=2,845) | 0.447 |

So **~79% of the headline gap survives** when every school in the comparison has complete data.
The score gap is mostly NU visiting genuinely stronger schools, not the index manufacturing a
gap from missing data. That is the reassuring half of the finding.

**Caveat on that number.** The full-coverage subset is not a random sample — it over-represents
schools that report everything, and never-visited schools in it are stronger than never-visited
schools overall (mean −0.024 vs −0.118). So 79% is an estimate conditional on a non-random
subset, not a clean partition of the two channels.

### Is "visited" just a proxy for affluence?

Partly, but modestly. Mean county child poverty is 12.67% for visited schools vs 15.92% for
never-visited — a real gap, but far smaller than the score gap it accompanies.

### What this means for the discovery list

The 4,218 schools absent from the admissions list are, almost by construction, never-visited.
They are therefore the population the index can least reliably score — 60.3% scorable versus
98.5%. The discovery story and the rigor story are in tension, and the deck should say so.

---

## Part 2 — thin coverage breaks the top tier

Chasing the top-tier anomaly above turned up a defect in the index itself.

### The finding

**74% of the "Most Demanding" tier (217 of 295 schools) is scored on 2 or fewer of the 5
components.** The breakdown of what top-tier schools actually scored on:

| Components used | Schools |
|---|---|
| `crdc_coursework` + `test_participation` | 154 |
| `test_participation` **alone** | 48 |
| all five | 26 |
| four | 40 |

55 of the 295 are scored on a **single component**.

Their profile versus the scored population: median dual-enrollment rate **0.795 vs 0.111**
(the 99th percentile overall is 0.885), median enrollment **200 vs 447**, and only 2 of the 217
have any AP performance data at all. By name they are overwhelmingly early-college and
dual-enrollment programs — "Early College High", "College Academy at Broward College",
"Career & Technical ECHS".

Meanwhile **New Trier — scored on 4 components with real AP and test data — sits at 1.329,
below the 1.924 cut, in Very Demanding.** It is outranked by 200-student early-college programs
carrying no AP data.

### Root cause

Proportional weight reallocation. A school with one available component gets a composite equal
to that single z-score, with weight reallocated to 1.0. A school with all five gets an *average*
of five, which regresses toward the middle. Coverage therefore determines variance:

| Components used | SD of `rigor_score` | % reaching top tier |
|---|---|---|
| 1 | 1.052 | **3.08%** |
| 2 | 0.689 | 1.86% |
| 3 | 0.736 | 1.01% |
| 4 | 0.688 | 1.81% |
| 5 | 0.513 | **0.32%** |

**A school scored on one component is roughly 10x more likely to reach "Most Demanding" than one
scored on all five** — purely as an artifact of how many numbers got averaged. This is the
classic composite-indicator failure mode: reallocation makes scores non-comparable across
different coverage patterns. It is not a rounding issue; it determines who is in the top tier.

### What it invalidates

- "295 schools, about one percent — a genuine national elite set." Three quarters of them are
  thin-data small schools, most with no AP performance signal.
- The golden-school sanity check. New Trier missing the top tier is not the model being strict;
  it is the model being wrong.
- The Part 1 top-tier anomaly (only 20.0% visited) — explained. The top tier is full of schools
  NU has never heard of because they are small early-college programs, not elite prep schools.

### Options, quantified

Requiring a minimum number of components before a school is tiered, with natural breaks refit on
the restricted population:

| Rule | Schools tiered | Top tier | Top-tier median enrollment | New Trier |
|---|---|---|---|---|
| current (≥1) | 21,951 | 295 | 200 | Very Demanding |
| **≥4 components** | 10,277 (47%) | 372 | 1,246 | **Most Demanding** |
| ≥5 components | 8,124 (37%) | 252 | 1,352 | — (not in subset) |
| ≥3 components | 11,464 (52%) | 20 | 438 | Very Demanding |

**≥4 looks like the defensible choice**: the top tier becomes real comprehensive high schools
(median enrollment 1,246), New Trier lands where readers expect, and it is consistent with the
principle already in the report — refuse to rank rather than guess. The cost is real and is the
client's call: the tiered population halves, from ~22,000 schools to ~10,300.

The ≥3 row is instructive on its own: 20 schools in the top tier. Natural breaks is unstable
against changes in the score distribution, which is a finding worth reporting regardless of
which rule is adopted.

A statistical alternative to a hard threshold is shrinkage — pull each score toward 0 in
proportion to how few components informed it. More principled, harder to explain to a counselor.
Not evaluated here.

**Recommendation: do not sign off the tiers until this is resolved.** It is a modeling decision
with a real coverage cost, so it belongs to the team and the client, not to a silent patch.

---

## Reproduce

```bash
cd etl
python build_visit_bias.py ../csv_exports/rigor_classification_v4_2026-07-24.csv \
    --version v4 --outdir ../csv_exports
```
