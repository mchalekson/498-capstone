# Team brief — Rigor model v3 (Week 5)

*One-page summary for the team meeting. Full detail in the linked docs.*

## The story in one paragraph

We upgraded the rigor classification from **v2 → v3**. The old model scored schools only on
what they **offer** (AP course counts, who signs up for the SAT). The research (and Bob) say
what matters is how students **perform** on the exams — so we pulled in AP exam scores and
SAT/ACT scores that were already in our data but never used. That reshuffled **~1 in 4 schools**
across tiers, and the tiers now **validate against independent data**: average SAT climbs
cleanly from the bottom tier (1052) to the top (1303). We also replaced the forced equal-fifths
buckets with natural breaks, so "Most Demanding" is a genuinely selective **700 schools**, not
an arbitrary top 20%.

## What changed (v2 → v3)

1. **Added exam performance** — AP exam score + SAT/ACT scores are now model components. The
   data confirms it: exam performance carries the most weight; "who took the test" carries
   almost none. → `docs/RIGOR_CLASSIFICATION.md`
2. **Realistic tiers** — natural breaks (Jenks), not equal fifths, per Bob's "not equal buckets"
   note. Top tier = 700 schools.
3. **Bob's "low offering / high scores" idea** — new AP-efficiency lens flags ~1,600 schools
   that offer few APs but score high ("do a lot with little"). Most sit *below* the top tier,
   so the model surfaces schools the tier alone hides. → `docs/RIGOR_ANALYSIS.md`
4. **Coverage by sector + STEM/grad-rate validation** — quantified the public vs private data
   gap, and checked the tier against grad rate & advanced-STEM (neither is a model input).
   → `docs/COVERAGE_BY_SECTOR.md`, `docs/RIGOR_ANALYSIS.md`

## Why we believe it (validation)

- **Independent SAT rises across tiers:** 1052 → 1115 → 1156 → 1219 → 1303 (no inversions).
- **Grad rate sharply separates the bottom tier** (67.6% vs ~86–90%).
- **Effective weights** confirm performance > availability — empirically, not just asserted.

## Honest caveats (say these — they build credibility)

- **Private schools are a blind spot** — the federal CRDC data is public-only (~0% private).
- **Exam-score data covers ~35% of schools**, skewed toward NU's recruiting universe.
- **Grad rate/STEM validate the bottom, not the very top** — "most demanding" = highest
  performance, not biggest course catalog, so those measures plateau/dip at the top.
- **We measure the school, not the student** — the tier describes an institution's
  opportunity+performance structure, not any individual applicant's coursework.

## Deliverables & suggested speaking split (per Wk5 "divide who speaks")

| Section | Doc | Owner? |
|---|---|---|
| Rigor model + why performance matters | `RIGOR_CLASSIFICATION.md` | |
| AP efficiency + "Bob's ideas" | `RIGOR_ANALYSIS.md` | |
| Data quality / coverage gaps | `COVERAGE_BY_SECTOR.md` | |
| Feature engineering / PCA + clustering | `CLUSTERING.md` | |
| SAT benchmarking / validation | `BENCHMARKING.md` | |
| Charts / live demo | `notebooks/EDA_Data_Analysis_Report.ipynb` | |

## Open decisions for the team

1. **Should exam performance stay weighted as-is?** It buys signal but adds mild SES
   correlation (−0.07 → −0.15, still weak). Keep, or down-weight?
2. **Natural breaks vs. quantiles for the final tiers?** We defaulted to natural breaks; both
   are in the output (`rigor_tier_*` vs `rigor_tier_*_quantile`).
3. **Is "AP efficiency" a headline deliverable or a supporting appendix?**
4. **Data ask for Bob:** per-course AP score distributions (Calc BC vs Calc BC across schools) —
   this is what would make the whole thing rigorous at the course level. Do we request it?

*All code runs green (77 tests). Rebuild any layer with the scripts in `etl/`.*
