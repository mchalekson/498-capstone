# Rigor analysis — AP efficiency + validation (Week-5 client ideas)

Two analytical layers on top of the v4 rigor tier, implementing ideas from the Week-5 Bob
meeting. Code: `etl/build_rigor_analysis.py` (run on `rigor_classification_v4_2026-07-24.csv`
→ `rigor_analysis_v4_2026-07-26.csv`). Neither changes the rigor composite — both are lenses
*on* it.

Note on the efficiency metric: it deliberately keeps the **raw mean AP exam score**
(`ap_score_nu`), not v4's `ap_qualifying_density`, because Bob's question is literally about
scores ("low AP offering / high AP scores"). Keeping the raw score here is also what makes this
a genuinely independent lens on the index rather than a restatement of one of its components.

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
| Below Average | 55 |
| Average | 836 |
| Demanding | 606 |
| Very Demanding | 97 |
| Most Demanding | 3 |

Only 3 of 1,597 land in "Most Demanding," because their thin AP catalog drags the composite
down — even though their students score as well as schools two tiers higher. **This is exactly
Bob's point, quantified:** ~1,594 schools do a lot with limited AP breadth, and the tier alone
hides them. For a recruiting use-case ("where do strong students emerge from limited
resources?"), `ap_efficiency` / the "Selective & effective" flag is arguably more actionable
than the tier itself. It should ship alongside the tier, not folded into it.

**v4 sharpens this finding rather than softening it.** Under v3 these schools clustered in
Demanding (872) with 307 reaching Very Demanding; under v4 the mass shifts down to Average (836)
and only 97 reach Very Demanding. Qualifying density multiplies performance by *volume* of exams
taken, so a school with few AP offerings now scores lower on the performance axis than it did
under a pure mean — the very schools this lens is designed to surface are pushed further down
the tier. The efficiency flag is therefore *more* necessary in v4, not less.

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

| Rigor tier | Mean grad rate | Mean advanced-STEM (0–4) | Calculus offered | n (STEM) |
|---|---|---|---|---|
| Below Average | 70.5% | 3.03 | 56% | 1,575 |
| Average | 86.5% | 3.33 | 71% | 6,089 |
| Demanding | 89.4% | 3.37 | 73% | 3,966 |
| Very Demanding | 89.5% | 3.41 | 74% | 1,037 |
| Most Demanding | 84.1% | 3.32 | 65% | 31 |

**Read honestly, this is a partial validation with an informative twist:**

- **The bottom tier is sharply separated** on both measures — Below Average schools graduate 19
  points lower (70.5% vs ~85–90%) and offer noticeably less advanced STEM (3.03 vs ~3.4) and a
  markedly lower Calculus rate. The tier clearly distinguishes genuinely under-resourced,
  lower-outcome schools. That is the validation working.
- **Advanced STEM is now cleanly monotonic through the first four tiers** (3.03 → 3.33 → 3.37 →
  3.41) — an improvement over v3, where it peaked at Demanding and fell back. Calculus tracks the
  same shape.
- **But the very top tier dips**, it doesn't peak — "Most Demanding" has a *lower* grad rate
  (84.1%) and slightly fewer advanced-STEM offerings (3.32) than "Very Demanding" (89.5% / 3.41).
  This is **not noise to smooth over — it's the same story as the efficiency finding above.** The
  natural-breaks top tier is driven by exam *performance*, so it captures the small, selective,
  high-scoring schools that do **not** have the broadest course catalogs (and whose grad rate
  is a near-ceiling ~85–90% shared with everything above the bottom tier). Grad rate saturates;
  it discriminates the floor, not the ceiling.
- **Caveat the top-tier cell explicitly**: v4's Most Demanding tier holds 295 schools, only 31 of
  which have CRDC STEM data. That row is a small, public-only, non-random subset — treat the dip
  as directionally consistent with the efficiency finding, not as a precisely estimated number.

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
