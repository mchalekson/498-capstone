# Presentation scripts — Week 6

Talk tracks for `docs/Bob_Week6_Update.pptx` (11 slides) and `docs/MSDS_498_Midterm.pptx`
(16 slides). Same material as the speaker notes in each deck, written out as continuous speech.

**Timing assumed** — Bob: 20 min talk + 10 min discussion. Midterm: 20 min. Adjust the cut
lists at the end of each section if your actual slot differs. Nobody should read this
verbatim; it's the spine, so everyone lands the same numbers and hands off cleanly.

**Every number below is in the deck and traceable to `csv_exports/`.** If you can't defend a
number, cut the sentence rather than soften it.

---

# Deck 1 — Bob & Adam (client update)

**The arc:** *"In Week 5 you asked for five things. Here's each one built, here's the evidence
it works, here's the one thing we need from you."*

Every slide traces to something they said. That's the whole design — they should recognise
their own requests coming back as work.

### 1 · Title (~20 sec)

> Thanks for the time. Quick framing before we start: almost everything in this deck came out
> of what you told us in Week 5 — the AP scores point, the low-offering/high-scores idea, and
> the question about coverage. So this is less "here's what we did" and more "here's what you
> asked for." We'll finish on one data ask.

### 2 · Where we are (~1 min)

> We're building a school-level measure of academic rigor from public data — something you can
> join to your own systems on CEEB. It's validated now: the tiers track real outcomes and
> they're not just a proxy for wealth, and I'll show you both of those.
>
> One scoping note I want to be upfront about, because it shapes everything: we're describing
> *the school an applicant came from*, not the applicant. This gives a reader context for a
> transcript. It doesn't rank students.

*Say the last paragraph deliberately. It prevents an expectation you can't meet.*

### 3 · How we measure rigor (~1.5 min)

> It's a weighted composite index — five standardized components averaged into one score. The
> important property is that it's decomposable: every tier walks back to the features that
> produced it. That's deliberately the opposite of Landscape, which people couldn't audit and
> which is part of why it went away.
>
> Following the research, and honestly following your Week-5 point, it's weighted toward how
> students *perform* on exams rather than what's on the course catalog.
>
> And we don't impute. If a school is missing data, we score it on what it has, or we don't
> score it at all. About 12,000 schools come out unscored, and we'd rather say that than
> invent a middle tier for them.

### 4 · Your ask: not equal buckets (~1.5 min)

> You pushed back on equal buckets, so here's the distribution. We use natural breaks — the
> cuts land at real gaps in the data rather than at fixed percentiles.
>
> "Most Demanding" ends up at 295 schools, not a forced top 20%. The middle tier holds 8,905,
> because that's genuinely where schools pile up.
>
> Worth knowing: natural breaks and equal-fifths agree on only about half of schools. So this
> wasn't a cosmetic choice — it materially changes who's in the top tier. If you ever want
> fixed-size tiers instead, we've kept that version on the shelf.

### 5 · What a school looks like (~1.5 min)

> This is what you actually receive per school: a tier, a score, a percentile, and the
> components underneath it — keyed on CEEB so it joins straight into your systems.
>
> New Trier as an example: Very Demanding, 96th percentile, and you can see it was scored on
> four of five components — we surface that rather than bury it.
>
> The point is a reader can see *why* a school landed where it did. That's what lets someone
> defend a decision later.

*Expect them to name a school and ask where it lands. If it's not on hand, say you'll follow
up — do not guess.*

### 6 · Your idea: low offering / high scores (~2 min)

> This one is yours directly — the schools that offer few APs but whose students score well.
> "Do a lot with little."
>
> There are 1,597 of them. And here's the finding: only three reach the top tier. A thin
> catalog drags the composite down no matter how well the students perform.
>
> So the index structurally *cannot* surface these schools. That's not something we can fix by
> reweighting — it's how an additive index behaves. Which is why we think this should ship
> alongside the tier as its own recruiting signal rather than get folded in.

*This is the slide where they see their own idea produced a real result. Give it room.*

### 7 · Data coverage (~1.5 min)

> You asked what the private-school number looks like. Here it is by sector, because a single
> overall number hides the problem.
>
> The federal CRDC data — AP participation, testtaker rate, graduation rate — is public-school
> only by law. So it's essentially zero percent for private schools. That's not a matching
> failure; the data doesn't exist.
>
> Which means private-school tiers rest almost entirely on your analytics block plus IB. It's a
> real blind spot and we'd rather name it than let you find it later.

### 8 · Does the tier mean something? (~1.5 min)

> The obvious question is whether this measures anything real. So we checked it against data
> the index never touched.
>
> Mean SAT rises across all five tiers — 1,066 up to 1,288, no inversions anywhere. The index
> was never built from SAT, so that's genuine external validation.
>
> Graduation rate separates the bottom tier sharply. But I want to flag something honestly:
> graduation rate plateaus and then dips slightly at the very top. That follows from what "most
> demanding" means here — highest performance, not biggest catalog. We're reporting it as we
> found it.

*Volunteer the dip. Being the one who raises it is worth more than the number costs.*

### 9 · It predicts outcomes (~1.5 min)

> Last validation. We modeled graduation rate from the opportunity features while controlling
> for socioeconomic status, which is the standard test in this literature.
>
> Opportunity adds about five points of R² beyond what SES alone explains — stable across
> specifications and model families.
>
> Now the honest tension: the *outcome* is heavily SES-driven — free-lunch rate dominates the
> model. But our *index* correlates with county poverty at only −0.11. So we're measuring
> opportunity structure, not laundering demographics. That distinction is the whole argument
> for building it this way.

### 10 · What we need from you (~2 min)

> Two things.
>
> The data ask: per-course AP score distributions — Calc BC at one school against Calc BC at
> another. That's what would let us verify rigor at the course level rather than the school
> level, and it's the single biggest upgrade available to us.
>
> The open question: the measurement vintage on the org export. We still don't know what year
> those SAT and AP averages describe, and it affects how we date the whole analysis.
>
> And a framing point — our tier is school-level, your counselor "most demanding coursework"
> field is per-student. Those complement each other rather than compete.

*Get a yes/no on the per-course data. Don't let it drift into "we'll look into it" again.*

### 11 · Next steps & discussion (~1 min, then open up)

> Where we're heading: tiering public and private separately, since they aren't built from the
> same data; validating against a second outcome; and packaging the methodology so your team
> can run it.
>
> What we'd most like from you: your read on the tier definitions, a decision on the per-course
> data, and which use case matters more — contextualizing applications you already have, or
> outreach.

### Q&A — Bob

| If they ask | Say |
|---|---|
| "Can this tell us who to admit?" | No, by design. It describes the school, so a reader can weigh a transcript in context. Student-level would need your internal outcomes — that's the handoff. |
| "Where does [school] land?" | Look it up live if you can; otherwise commit to following up. Never guess. |
| "Isn't this just ranking rich suburbs?" | Poverty correlation is −0.11. Mean SAT, by comparison, is −0.385. Measuring opportunity instead of outcomes is exactly what buys that. |
| "Why is [good school] only Very Demanding?" | Tiers are relative to our scored population and natural-breaks cuts are strict — the top tier is 295 schools nationally. Walk them through the components. |
| "What about private schools?" | Structural blind spot — federal data is public-only. Their tiers rest on your data plus IB. It's on the coverage slide. |
| "How current is this?" | CRDC 2021-22, graduation rate is a COVID cohort. And we still need the vintage on your export. |

---

# Deck 2 — Midterm (methods defense)

**The arc:** *"Admissions lost its standardized school-context tool. We rebuilt one from public
data, every choice is auditable, and we validated it against data it was never built from."*

Where the client deck sells the result, this one defends the method. Assume the audience is
looking for the weak seam — so name the weaknesses before they do.

### 1 · Title (~15 sec)

> College Board discontinued Landscape last September, and admissions offices lost their
> standardized way of understanding an applicant's high school. We rebuilt that from public
> data.

### 2 · Problem & objective (~1.5 min)

> Landscape was discontinued in September 2025. Roughly a quarter of applicants arrive with no
> school-context profile at all.
>
> The reader's problem is concrete: the same transcript means different things at different
> schools. Four APs where twenty are offered is a different signal from four where four exist.
>
> So our objective is a transparent, reproducible measure of a school's academic rigor — so
> coursework can be read in the context of what the school actually offered.
>
> One thing we want to be precise about, because it constrains everything: we measure schools,
> not students. There's no admissions outcome anywhere in this data, so there's no admit model
> here and we won't claim one.

### 3 · Data & pipeline (~1.5 min)

> Six sources: NCES, the federal civil rights data collection, Census finance and poverty data,
> Northwestern's own export, IB, and Illinois state data. About 34,000 high schools.
>
> The whole thing is a Dockerized ETL — it re-runs end to end without engineering support, so
> when a new data vintage lands the client can rebuild rather than call us.
>
> Every variable carries its source and vintage in a data dictionary. That was a client
> requirement and it's also what makes the limitations section honest later.

### 4 · Record linkage (~2 min)

> First real technical problem: CEEB codes and NCES IDs have no common key. No shared
> identifier at all.
>
> We use a three-way decision rule — auto-accept, human review, reject — which is the
> Fellegi–Sunter framework from 1969. The reason it's three-way rather than binary matters: if
> you force every borderline pair into match-or-no-match, you inject false links that
> contaminate everything downstream and you never see them again.
>
> Similarity is token-based rather than edit distance, because school names reorder words more
> than they misspell them.
>
> And for the ambiguous middle band — the pairs a threshold genuinely can't settle — we use an
> LLM to adjudicate, with every decision logged and auditable. That's the AI component: it's
> resolving entity ambiguity, not scoring schools.

### 5 · The rigor index (~1.5 min)

> The index is a weighted composite: five components, transparent and decomposable.
>
> The organizing principle comes from Geiser and Santelices — exam *performance* predicts
> college outcomes, course *availability* largely doesn't. So performance carries the weight.
>
> Where a school is missing a component we reallocate weight proportionally across what's
> available rather than impute — imputation would manufacture signal we don't have.
>
> One refinement worth naming: we replaced mean AP score with qualifying density — expected
> passing exams per student. A mean rewards gatekeeping. A school that only lets its strongest
> students sit the exam posts a beautiful average; an open-access school gets punished for
> breadth. Density fuses opportunity and performance instead.

### 6 · Nominal vs. effective weights (~2 min)

> A composite-index problem people usually skip: the weights you assign aren't the influence
> features actually have, once they're correlated.
>
> So we decomposed it. AP performance was assigned 0.20 but contributes 0.31 of the variance.
> Test participation was assigned 0.15 and contributes 0.08 — it's almost entirely absorbed by
> the other components.
>
> Then the sensitivity analysis, which is the number I'd point at: drop the performance
> components entirely — that's essentially our earlier model — and 30% of schools change tier.
> Equal weighting only moves 7%.
>
> So the index is robust to reasonable reweighting, but genuinely sensitive to the one change
> the literature told us to make. That's evidence the change was substantive rather than
> cosmetic.

### 7 · From score to tiers (~1.5 min)

> Turning a continuous score into five tiers is a separate decision, and we made it explicitly.
>
> We use Jenks natural breaks — which is 1-D k-means — cutting where the distribution actually
> gaps. The alternative is equal quantiles, and Reardon's work cautions specifically against
> splitting schools that differ only slightly, which is exactly what quantiles force you to do.
>
> Result: 295 schools in the top tier, not a mandated top fifth.
>
> The caveat we state out loud: these cuts are norm-referenced — relative to our scored
> population, not to an absolute standard. Run it on a different population and the boundaries
> move. A criterion-referenced version is a real alternative if a client wants stability.

### 8 · Results (~2 min)

> Here's what actually comes out. 21,951 schools scored; 12,441 left unscored rather than
> imputed.
>
> Left to right: tier sizes. Then mean AP exam score climbing 2.06 to 3.56 — that's an index
> input, so it's an internal consistency check, not evidence.
>
> Then the two that matter. Mean SAT climbs 1,066 to 1,288 — never an input. And graduation
> rate separates the bottom tier hard, 70% against high-80s.
>
> Then it plateaus, and dips at the top tier. We're showing that rather than cropping it. It
> follows from the construct: "most demanding" means performance, not catalog size, and
> graduation rate saturates well before the top.

### 9 · What comes out per school (~1 min)

> At the school level you get a tier, a score, a percentile, and the components behind it.
>
> New Trier: Very Demanding, 96th percentile, scored on four of five components — and the
> missingness is part of the output, not a footnote.
>
> Decomposability is the design requirement. Landscape's problem was that nobody could
> interrogate the number.

### 10 · Validation (~1.5 min)

> The core validation. SAT rises monotonically across all five tiers, a 222-point spread, no
> inversions — on a measure the index never touched.
>
> That's the strongest single piece of evidence we have that the tiers track something real
> rather than reproducing our own assumptions.
>
> Alongside that, a face-validity audit on known schools, because a measure that's
> statistically clean and intuitively absurd is still wrong.

### 11 · Why opportunity, not test scores (~2 min)

> The obvious objection is: why build any of this? Just rank schools by mean SAT.
>
> So we tested it. SAT correlates with county child poverty at −0.385. Our tier: −0.110. An
> outcome measure is about three and a half times more socioeconomically confounded than an
> opportunity measure.
>
> That's the argument for the whole design — and it's now our own empirical result rather than
> a citation. The literature predicted it; we measured it in our data.
>
> It's also the honest counterweight to the previous slide: we're not claiming the tier is free
> of SES. We're claiming it's substantially less entangled than the obvious alternative, and we
> quantified how much.

*If you cut anything, don't cut this slide.*

### 12 · Predictive validation (~2 min)

> This is the supervised layer, and I want to be precise about its role: it validates the
> index, it isn't the product.
>
> Gradient boosting with a linear baseline, predicting graduation rate from opportunity
> features with SES controlled. 80/20 held-out split, fixed seed, permutation importance over
> ten repeats, metrics on the test set only.
>
> Opportunity adds about 0.05 R² beyond SES — stable across two specifications and both model
> families.
>
> And the finding we don't hide: free-lunch rate dominates the model at 0.53 importance. The
> outcome is SES-driven. But the index itself correlates with poverty at −0.11 — which is
> precisely the case for measuring opportunity structure instead of outcomes when you're
> comparing schools.

### 13 · Unsupervised segments (~1.5 min)

> The unsupervised layer. K-means and hierarchical clustering over PCA components retaining 90%
> of variance, across region, academic profile, and funding.
>
> k=4 by the gap statistic, cross-checked against silhouette, and we compared the two
> algorithms with adjusted Rand index.
>
> Design decision: we deliberately excluded the rigor score from the clustering inputs. If it
> were in there, asking "do the clusters agree with the tier?" would be circular.
>
> The finding: every cluster spans several tiers. So segments are a genuinely different cut of
> the data, not the tier relabeled.
>
> Limitation: complete-case requirements drop this to 5,801 schools, against 21,951 for the
> tiering. Much narrower, and we report it that way.

### 14 · Three-layer system (~1.5 min)

> Stepping back — three layers, each doing something the others can't.
>
> The measurement model is the composite index; that's the deliverable. Unsupervised ML gives
> the segments. Supervised ML does the validation.
>
> The question we expect: why isn't the tier itself a trained model? Because no ground-truth
> rigor label exists anywhere. Nobody publishes a dataset saying "this school is Most
> Demanding." To train a classifier we'd have to invent the labels — and then the model just
> reproduces our assumptions with a confusion matrix stapled on, and nothing could falsify it.
>
> So: an auditable measurement instrument, validated by machine learning rather than produced
> by it. We think that's the more defensible architecture given the data that exists.

*This is the slide that carries the deck if the architecture gets challenged. Know it cold.*

### 15 · Limitations (~1.5 min)

> Five, briefly.
>
> Ecological inference — we measure schools, not students, and school-level findings don't
> transfer to individuals.
>
> Levels, not growth — Reardon's caution about achievement measures reproducing SES ordering;
> we ran the confounding check rather than assert we're clean.
>
> Coverage — performance data covers about 35% of schools and skews toward Northwestern's
> recruiting universe.
>
> The private-school blind spot — federal data is public-only.
>
> And fragility: losing CRDC access would reshuffle around 40% of the covered population. That
> dependency is worth stating plainly.
>
> Most of these map onto the client handoff as extension points rather than dead ends.

### 16 · Next steps (~1 min)

> Weeks 7 through 10: separate public and private tiering, since the available features differ
> structurally. A second outcome for validation, and a post-COVID graduation vintage when it
> publishes. A handoff guide. Then the final report.
>
> The measure is built to be recalibrated against Northwestern's internal outcomes — that's the
> natural continuation.

### Q&A — midterm

| If they ask | Say |
|---|---|
| **"Where's the machine learning?"** | Three layers — slide 14. Gradient boosting for validation, k-means/hierarchical for segments, and Jenks is 1-D k-means. The deliverable is a measurement instrument by design, because no ground-truth label exists. |
| "Why not train a classifier for the tier?" | Nothing to train against. We'd have to invent labels, and the model would then be unfalsifiable. |
| "How do you know the tiers are right?" | We don't have ground truth, so we validate externally: SAT rises monotonically across all five and it was never an input. Plus a face-validity audit. |
| "Isn't this just measuring wealth?" | Poverty correlation −0.11, against −0.385 for mean SAT — slide 11. Less confounded than the obvious alternative, and quantified. |
| "Why five tiers?" | We inherited the client's counselor vocabulary. The number is a client constraint; the *boundaries* are algorithmic. |
| "Why natural breaks over quantiles?" | Quantiles split near-identical schools — Reardon's caution. The two schemes agree on only ~half of schools, so it matters. |
| "Is 35% coverage enough?" | It's honest rather than sufficient. We never impute, we report per-sector coverage, and unscored schools stay unscored. |
| "What's the LLM actually doing?" | Adjudicating ambiguous record matches — slide 4. Entity resolution, not scoring. Every decision logged. |
| "Could this be biased against under-resourced schools?" | It's a real risk and why we built from opportunity rather than outcomes. Slide 11 is the evidence. It's still a limitation, not a solved problem. |

---

## Suggested speaking split

Fills the empty owner column in `TEAM_BRIEF.md`. Adjust to who's most fluent where — the only
rule is that whoever presents slide 14 must be able to defend the architecture unscripted.

| Presenter | Bob deck | Midterm deck |
|---|---|---|
| A | 1–2 (framing) | 1–3 (problem, data) |
| B | 3–5 (index, tiers, output) | 4–7 (linkage, index, weights, tiering) |
| C | 6–7 (their idea, coverage) | 8–11 (results, validation, SES) |
| D | 8–11 (validation, asks, next) | 12–16 (models, limitations, next) |

Hand off *between* sections, never mid-argument. Whoever isn't speaking tracks time.

## If you're short on time

**Bob deck** — merge 4 and 5 into one "here's the output" beat. Never cut 6 (his idea) or 10
(the data ask); those are the reasons for the meeting.

**Midterm** — cut 9 (folds into 8) and compress 15 to three spoken limitations. Never cut 11 or
14 — they're the two slides that answer the hardest questions you'll get.

## Before you present

- [ ] Team names on the midterm title slide (`TEAM` in `etl/build_decks.py`)
- [ ] Export both decks to PDF as a projector fallback
- [ ] Rehearse slides 11 and 14 of the midterm out loud — they're argument, not description
- [ ] Have `csv_exports/rigor_classification_v4_2026-07-24.csv` open in case Bob names a school
- [ ] Confirm the midterm time limit; this script assumes 20 minutes
