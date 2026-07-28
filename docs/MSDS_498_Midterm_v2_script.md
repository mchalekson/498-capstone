# Speaker Script — NU Capstone Midterm Report

Aligned to `MSDS_498_Midterm_v2.pptx` (12 slides). Target length ≈ 10–12 minutes. Stage directions in *italics*.

---

## Slide 1 — Title *(≈30 sec)*

Good afternoon, everyone. I'm presenting our midterm report for the NU Capstone project.

Over the past six weeks, our team has been building something with a simple ambition behind it: **every U.S. high school, one trusted picture**. Today I'll show you what we built, how it connects to the admissions office's existing world, and what our rigor model reveals — including a few things nobody was expecting to find.

---

## Slide 2 — Why Now *(≈1 min)*

Let me start with why this project matters right now.

Admissions never reads an applicant in a vacuum — every file is read in the context of the applicant's high school. But the reference data for that context is fragmented across a dozen disconnected systems.

The in-house school list has grown organically for decades. It's rich where NU actively recruits — and nearly silent everywhere else.

And there's a market gap: when College Board withdrew its Landscape tool in 2019, it left no transparent replacement. Nothing credible has filled that space.

Meanwhile, federal open data has quietly matured to the point where a verified, national, annually refreshable picture is actually possible. That's the window we're stepping into.

---

## Slide 3 — The Data Behind It *(≈1 min)*

Here's the foundation. We unified six families of sources into one master database.

*(gesture across the diagram)* Federal education data gives us every school's verified identity, coursework, and outcomes. The College Board world contributes the CEEB codes admissions runs on. The IB Organization tells us who's authorized to offer the diploma. State and local sources add depth for Illinois and Chicago. Census data describes each school's community. And finally — the admissions office's own export brings the SAT and AP performance depth that only NU has.

The design principle: public sources give us national coverage and verifiability; NU's own data gives us depth. Neither replaces the other.

---

## Slide 4 — What We Built *(≈45 sec)*

The result, in three numbers: **25,577** verified public and private high schools. **127** data points per school. **Eleven** systems, unified in a single pipeline.

And I want to stress the last bullet: this isn't a one-off spreadsheet. The entire database rebuilds with one command whenever new data years are released. It's an asset that stays current.

---

## Slide 5 — Integration *(≈1 min)*

A platform is only useful if it plugs into how admissions already works. So we linked every school to the CEEB codes the office uses daily.

*(point to donut)* 83.5 percent of our schools are now connected to the admissions list. Getting there wasn't trivial — school names are messy. The same school appears as "Alief Hastings" in one system and just "Hastings" in another; names get renamed, abbreviated, truncated.

Our matching engine handles those quirks with rules first, and an AI reviewer adjudicates the genuinely ambiguous cases — with every decision recorded and reversible.

And we verified the result independently: where both systems have coordinates, matched records agree to about one kilometer. The links aren't just plausible — they're physically confirmed.

---

## Slide 6 — Discovery *(≈1.5 min — the money slide, slow down)*

Now the part I'm most excited about. That green slice from the last slide? Those are **4,218 real, verified high schools that aren't on the admissions list at all.**

Most are small. But 421 of them have more than five hundred students, and forty-one offer the IB Diploma.

And here's the finding that surprised us: five of the largest missing schools are 3,000-student suburban campuses — in Miami, Orlando, Tampa, Denver, and Houston — all opened in the early 2000s. Their neighboring schools are on the list; these aren't. The list appears to have a blind spot for an entire construction wave of American suburbs.

We've packaged all of this as a ranked prospect list, with each school's academic profile attached. This is new recruiting territory, discovered simply by connecting data the list never touched.

---

## Slide 7 — How the Rigor Score Is Built *(≈1.5 min)*

Now to the analytical core: classifying every school's academic rigor. Before showing results, let me explain how the score works — because *how* it works is the point.

*(point to donut)* Five ingredient families, with weights we assigned deliberately: what AP opportunities a school offers, how its students actually perform on AP exams, its broader advanced coursework including IB, and test performance and participation. Performance signals carry the most influence — the research is clear that performance, not mere availability, is what predicts college success.

Three design choices matter. First, missing data never punishes a school: weights reallocate to whatever a school actually reports, and schools with no signal simply aren't scored — never dumped into a middle tier. Second, tier boundaries fall at natural gaps in the score distribution, not forced quotas. Third, we stress-tested the whole thing: under alternative weightings, school rankings barely move.

This is a transparent index in the academic tradition — every school's score can be decomposed and explained to a counselor or a dean.

---

## Slide 8 — Five Transparent Tiers *(≈45 sec)*

Here's what that produces: five tiers across nearly 22,000 scored schools.

Notice the shape — it's not a bell curve by decree. "Most Demanding" is earned by just 295 schools, about one percent. That label now means something: a genuine national elite set, schools combining broad access to advanced coursework with strong results.

And the sanity check passes: landmark schools land exactly where experienced admissions readers would expect them.

---

## Slide 9 — Fairness *(≈1.5 min — second money slide)*

Here's the slide I'd defend hardest in any room.

The obvious objection to ranking high schools is: "aren't you just ranking wealth?" That criticism is exactly what sank College Board's Landscape.

So we measured it. *(point to chart)* Raw SAT scores correlate with community poverty at minus 0.39 — test scores largely mirror wealth. Our rigor tier? Minus 0.11. A fraction of that.

Why? Because we measure the **opportunity structure** — what a school offers its students — not outcomes that track family income.

And we validated it independently: what a school offers genuinely predicts student outcomes, over and above demographics. So the tier is informative *and* it isn't a wealth proxy. That combination is what Landscape never managed to demonstrate — and it's this platform's strongest claim.

---

## Slide 10 — The Models We Use *(≈45 sec)*

Briefly, what's under the hood — four models, each with a job.

The rigor tiers: a transparent weighted index, deliberately not a black box. School groupings: classic clustering to find families of similar schools. Validation: regression models confirming the index predicts real outcomes. And record matching: a rule engine that resolves about 88 percent of cases deterministically, with AI judging only the hard cases — fully audited.

One principle throughout: statistical models stay simple and explainable; AI is used only where judgment is needed, and it always leaves an audit trail.

---

## Slide 11 — Roadmap *(≈45 sec)*

Where we take it next, in four steps.

One: model sign-off — team and client review of the tiers before adoption. Two: putting the discovery list into recruiting hands, sorted by fit. Three: going deeper on private schools, using AI to extract data from the profiles schools already publish. Four: full annual-refresh automation — one command, and the platform updates itself and reports what changed.

---

## Slide 12 — Close *(≈30 sec)*

To sum up: today you've seen a working platform — a national database, live integration with the admissions list, a defensible rigor classification, and four thousand schools of new recruiting territory.

What we need next is straightforward: sign-off on the model, and the discovery list in recruiters' hands.

Thank you — happy to take questions.

---

## Anticipated Q&A *(backup)*

- **"How accurate is the matching, really?"** — Three independent checks: exact official codes for two-thirds of links; geographic verification at ~1 km; and every AI-adjudicated case is logged and reversible. The ambiguous residue is flagged, not guessed.
- **"Why should we trust a tier over test scores?"** — We're not replacing scores; we're adding context that scores can't give. And unlike scores, the tier barely correlates with community wealth — that's measured, not asserted.
- **"What about private schools?"** — Federal collections cover them thinly; that's a structural gap, not a pipeline flaw. It's the reason step 3 of the roadmap is AI extraction from published school profiles.
- **"Is the data current?"** — School rosters are 2024-25. Some outcome measures are COVID-era and will be refreshed as federal releases catch up — the pipeline is built for exactly that.
