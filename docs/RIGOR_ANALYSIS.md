# Rigor analysis — AP efficiency + validation (Week-5 client ideas)

Two analytical layers on top of the v3 rigor tier, implementing ideas from the Week-5 Bob
meeting. Code: `etl/build_rigor_analysis.py` (run on `rigor_classification_v3_2026-07-24.csv`).
Neither changes the rigor composite — both are lenses *on* it.

---

## (1) AP efficiency — "low AP offering / high AP scores"

**The problem Bob named.** The rigor composite *adds* offering breadth and exam performance, so
a big school offering 25 APs at mediocre scores outranks a small school offering 5 APs where
students ace them. Bob's interest is the school that punches **above** its offering weight.

**The signal.** `ap_efficiency = z(AP exam score) − z(AP tests offered)`, plus a 2×2 quadrant on
the medians, computed on the **10,504** schools with both signals:

| Quadrant | Schools |
|---|---|
| Broad & high-performing (many offered, high scores) | 3,687 |
| Limited (few offered, low scores) | 3,429 |
| Broad but underperforming (many offered, low scores) | 1,791 |
| **Selective & effective (few offered, high scores)** — *the Bob case* | **1,597** |

**The finding that matters.** Those 1,597 "selective & effective" schools — few AP offerings but
strong exam outcomes — are almost all ranked **below** the top rigor tier by the additive
composite:

| Rigor tier of the "Selective & effective" schools | Schools |
|---|---|
| Below Average | 2 |
| Average | 407 |
| Demanding | 872 |
| Very Demanding | 307 |
| Most Demanding | 9 |

Only 9 of 1,597 land in "Most Demanding," because their thin AP catalog drags the composite
down — even though their students score as well as schools two tiers higher. **This is exactly
Bob's point, quantified:** ~1,586 schools do a lot with limited AP breadth, and the tier alone
hides them. For a recruiting use-case ("where do strong students emerge from limited
resources?"), `ap_efficiency` / the "Selective & effective" flag is arguably more actionable
than the tier itself. It should ship alongside the tier, not folded into it.

---

## (2) Validation — grad rate & advanced-STEM by tier (neither is a model input)

Both were named by Bob as school-comparison signals. They are deliberately **kept out of the
composite** — grad rate is an SES-confounded *outcome* (the Week-6 plan holds it out as a
validation check, per the SEDA caution), and advanced-STEM is public-only CRDC *availability*
(the weak signal, ~0% for private schools). Used here as independent checks: if the tier is
meaningful, both should rise with it **without having been inputs.**

Advanced-STEM = count (0–4) of Calculus / Advanced Math / Chemistry / Physics offered, from the
CRDC 2021-22 course files (`etl/clean_crdc_stem.py` → `crdc_stem_clean.csv`), joined by
`ceeb → nces_id_12`. Public schools only.

| Rigor tier | Mean grad rate | Mean advanced-STEM (0–4) | Calculus offered |
|---|---|---|---|
| Below Average | 67.6% | 2.83 | 47% |
| Average | 85.9% | 3.32 | 71% |
| Demanding | 89.5% | 3.43 | 75% |
| Very Demanding | 89.5% | 3.36 | 73% |
| Most Demanding | 86.2% | 2.96 | 56% |

**Read honestly, this is a partial validation with an informative twist:**

- **The bottom tier is sharply separated** on both measures — Below Average schools graduate 18
  points lower (67.6% vs ~86–90%) and offer noticeably less advanced STEM (2.83 vs ~3.4) and
  half the Calculus rate. The tier clearly distinguishes genuinely under-resourced,
  lower-outcome schools. That is the validation working.
- **But the very top tier dips**, it doesn't peak — "Most Demanding" has a *lower* grad rate
  (86.2%) and *fewer* advanced-STEM offerings (2.96) than "Demanding" (89.5% / 3.43). This is
  **not noise to smooth over — it's the same story as the efficiency finding above.** The
  natural-breaks top tier is driven by exam *performance*, so it captures the small, selective,
  high-scoring schools that do **not** have the broadest course catalogs (and whose grad rate
  is a near-ceiling ~86–90% shared with everything above the bottom tier). Grad rate saturates;
  it discriminates the floor, not the ceiling.

**Takeaway for the writeup:** grad rate and STEM breadth validate that the tier correctly
identifies low-opportunity schools, but they do **not** monotonically track the top of the
distribution — because "most demanding" here means highest exam performance, not biggest
catalog. State this rather than claiming clean monotonicity; it is consistent with, and
reinforces, the AP-efficiency result.

---

## Outputs

- `rigor_analysis_v3_2026-07-24.csv` — per school: `ap_efficiency`, `ap_efficiency_quadrant`,
  `stem_advanced_offered`, `calculus_offered`, `physics_offered`, alongside tier/score/grad.
- `crdc_stem_clean.csv` — the reusable advanced-STEM availability table (keyed `nces_id_12`).

## What would strengthen this (data asks for Bob)

- **Per-course AP score distributions** would let "Selective & effective" be verified at the
  course level (are the few APs they offer the hard ones — Calc BC, Physics C?), turning the
  efficiency signal from suggestive to rigorous. This is the same per-course ask flagged in the
  rigor discussion.
