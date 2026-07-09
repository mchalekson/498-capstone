# Literature Review

*AI-Driven High School Data Intelligence Platform — MSDS 498 Capstone, Summer 2026*

---

> **Two findings in this review contradict claims currently in the project plan.** Both are load-bearing, so they are stated up front rather than buried in the narrative.
>
> **1. The plan states that "no public source publishes school-level AP participation" (§2.3.2, §3.2.1).** This is not correct. The U.S. Department of Education's **Civil Rights Data Collection (CRDC)** is a mandatory biennial census of every public school and district receiving federal funds — over 98,000 schools — and its school-level public-use file includes the number of distinct AP courses offered, AP course enrollment, IB Diploma Programme enrollment, dual-enrollment participation, SAT/ACT participation, and advanced math/science course offerings. It is keyed to NCES identifiers, so it joins to `nces_public_schools_clean` on a direct ID with no fuzzy matching. It does not appear to publish AP *exam scores* at school level, so the distinction below between AP coursework and AP performance still binds. But CRDC substantially reduces the project's dependency on Bob's College Board institutional-access request, and it also supplies a school-level IB indicator that may make the DevTools-scraped `ib_us` file redundant or, better, verifiable against an independent source. **This should be investigated before Week 5 feature engineering begins.**
>
> **2. The College Board discontinued *Landscape* in September 2025.** Landscape is the closest existing analogue to what this project is building — a standardized, publicly-sourced summary of an applicant's high school and neighborhood context, distributed to admissions offices. Its withdrawal, and the policy environment that produced it, is almost certainly the "vendor discontinued school-level data delivery" event described in §1.2 of the plan. This reframes the business case (the capability was withdrawn for policy reasons, not commercial ones) and it means §2.8's assertion that "no government approval, socio-cultural, or gender-related considerations apply" is difficult to sustain. Section 3 below treats this at length.

---

## 1. Scope and Approach

This review covers four literatures that the platform sits at the intersection of: (1) what academic rigor is and whether it predicts anything, (2) prior attempts to deliver school context to admissions officers, (3) the measurement literature on constructing school-level composite ratings, and (4) the record-linkage and reproducibility methods the pipeline depends on. The organizing question throughout is not "has this been done?" but "what does the evidence say about the specific design choices already made in this project?" — because the pipeline is largely built, and the value of a review at this stage is to identify which choices are well-supported, which are under-supported, and which are contradicted.

---

## 2. Academic Rigor: Construct and Predictive Validity

### 2.1 The foundational claim

The strongest empirical support for the project's premise comes from Adelman's two U.S. Department of Education longitudinal studies. *Answers in the Tool Box* (Adelman, 1999) followed the High School & Beyond sophomore cohort and found that a composite measure of "academic resources" — dominated by the intensity and quality of the high school curriculum — was the single strongest predictor of bachelor's degree completion, alongside continuous enrollment. The model accounted for roughly 43% of variance in degree completion. Crucially for admissions practice, Adelman concluded that admissions formulas emphasizing test scores and GPA *over* curriculum intensity are likely to produce lower degree-completion rates.

*The Toolbox Revisited* (Adelman, 2006) replicated this on the NELS:88/2000 cohort and strengthened the finding: academic curriculum intensity mattered *more* than in the original study, while senior-year test scores mattered less — Adelman's reasoning being that curriculum represents a three-to-four-year investment while a test represents three to four hours. Adelman operationalized intensity as a 31-level gradation of Carnegie units, highest math level reached, and AP course count; students in the top quintile of that measure earned bachelor's degrees at a 95% rate.

**Implication for this project.** Adelman's work justifies the *existence* of a rigor variable and justifies building it from curriculum offerings rather than from test scores. It does not, however, validate a *school-level* rigor tier: Adelman measured individual student transcripts, not school characteristics. Inferring a student's curricular intensity from their school's course catalog is an ecological inference, and the project should say so explicitly rather than cite Adelman as though he validated the school-level construct.

### 2.2 The central complication: offerings versus performance

Geiser and Santelices (2004), examining University of California admissions, found that the *number* of AP and honors courses a student took had little to no validity in predicting college outcomes once other factors were controlled, while performance on AP *examinations* was a strong predictor. They concluded that UC's practice of awarding bonus points for AP enrollment lacked predictive justification. The College Board's response (Camara & Michaelides, 2005) disputed the framing but did not dispute the core empirical result — that coursework alone contributes little and exam performance contributes a lot. Subsequent work has largely converged on this: whatever the disagreement about effect sizes, there is broad consensus that passing the AP exam, not enrolling in the AP course, is what carries signal.

This is the most consequential finding in this review for the rigor model as currently specified. **The model is being built primarily from availability data** — IB programme authorization flags (which, as the team has already documented, contain no exam scores for U.S. schools), state-level AP aggregates, and, if adopted, CRDC's AP course counts and enrollment. Availability is precisely the variable Geiser and Santelices found to be weakest. The rigor tiers will therefore measure *opportunity structure* — what a school offers — rather than *academic outcome*. That is a defensible and useful thing to measure, and it is what an admissions office planning school visits arguably needs. But it should be named as such in the paper. A tier labeled "Most Demanding" implies an outcome claim the data cannot support; a tier labeled "Most Opportunity-Rich" or similar does not.

### 2.3 Availability is confounded with poverty and school size

Kolluri's (2018) review of the AP literature in *Review of Educational Research* documents both the expansion of AP access and its persistent stratification: students from low-income families enroll in AP, where it is offered, at less than a third of the rate of middle- and high-income students, and parental education independently predicts enrollment at roughly a 2:1 ratio. Kolluri also notes a methodological weakness across the AP-effectiveness literature — of the quantitative studies reviewed, nearly all were correlational and could not rule out student- and school-level confounding.

The U.S. Government Accountability Office (2018, GAO-19-8) found directly that public high schools with more students in poverty and smaller schools provide fewer academic offerings to prepare students for college.

**Implication.** A rigor tier built from course-offering counts will be substantially a proxy for school size and school affluence. This is not a fatal objection — a small rural school genuinely does offer fewer AP courses, and an admissions officer benefits from knowing that — but it means the tier cannot be interpreted as a measure of school quality or of student preparation, and it means the project's own funding/poverty overlay (§2.4 of the plan) is not an independent enrichment layer but is *collinear with the rigor outcome itself*. Any PCA or feature-selection step in Weeks 5–6 should expect this and should report the correlation between the poverty/finance features and the rigor score explicitly.

### 2.4 IB-specific evidence

Evidence on the IB Diploma Programme is more favorable but subject to the same selection concerns. Coca, Johnson, and Kelley-Kemple (2012), studying Chicago Public Schools IBDP graduates from 2003–2007 against a matched comparison group, found IBDP students were roughly 40% more likely to attend four-year colleges and 50% more likely to attend more selective colleges, with significantly higher two-year persistence. Because this study is CPS-based and uses a matched design, it is unusually well-suited as a citation for the project's Chicago/CPS Opportunity Index pilot region.

However, the broader IB literature is candid that IB students are a self-selected population and that most studies do not adequately address this. The IB's own commissioned research reports strong postsecondary outcomes but frequently compares IB students to national averages rather than to matched controls. The project should cite Coca et al. rather than IB-published outcome studies where possible.

---

## 3. Prior Art: Delivering School Context to Admissions Offices

### 3.1 The evidence base

Bastedo and colleagues have produced the most rigorous evidence that school-context data changes admissions behavior. In field experiments with admissions officers at eight universities re-reading real applications alongside a dashboard of contextual high school and neighborhood data, officers at institutions practicing holistic review were more likely to recommend admitting low-SES applicants when given contextual data; readers were also primed to evaluate applicants from highly disadvantaged contexts more favorably, an effect that persisted even for participants not shown the dashboard (Bastedo, Bell, Howell, Hsu, Hurwitz, Perfetto, & Welch, 2022). The authors are careful to note that fidelity to holistic practice is a precondition for the effect.

Bastedo, Umbricht, Bausch, Byun, and Bai (2023, *AERA Open*) extended this from admissions *behavior* to student *outcomes*, finding that contextualized measures of high school performance — a student's grades and course-taking relative to their own school's distribution — were strongly associated with college success, and that contextualized high school GPA had a stronger relationship with success than contextualized test scores. The same paper documents a gap this project is well positioned to fill: high school profiles have no standardized format and are not always submitted, leaving admissions officers without high school context on roughly 25% of applications, with public and majority-low-income schools least likely to supply it.

**This is the strongest available justification for the project's existence**, and it is a stronger one than the "we lost a vendor" framing in the current business case. The literature says: context data measurably improves both equity and prediction, and roughly a quarter of applicants arrive without it.

### 3.2 The cautionary history

The College Board's own attempt at this is instructive. The Environmental Context Dashboard, piloted from 2016 and publicized in 2019, compiled school and neighborhood indicators (free/reduced-price lunch share, AP participation, median family income, crime rates, college-going rates) and reduced them to a single 1–100 score. The press labeled it the "adversity score." Within months, following widespread criticism that a single number could not represent a student's circumstances, College Board CEO David Coleman conceded the single score was a mistake and the tool was relaunched as *Landscape*, presenting the same underlying indicators as separate school and neighborhood measures with no composite score.

Landscape ran until September 2025, when the College Board discontinued it, citing evolving federal and state policy "around how institutions use demographic and geographic information in admissions." The context was the post-*SFFA v. Harvard* environment, an August 2025 executive order requiring institutions to demonstrate they were not using "hidden racial proxies," and a Department of Justice memo warning that geographic recruiting could be unlawful as a race proxy. Students for Fair Admissions had publicly targeted the tool. Commentators across the political spectrum — including Kahlenberg, who served as an SFFA expert witness and had favorably cited Landscape in that capacity — described the withdrawal as legally unnecessary, noting that several justices in *SFFA* explicitly endorsed socioeconomic factors as a permissible route to diversity. Research on Landscape's actual effects (Mabel and colleagues, 2022) found that it modestly increased admission offers to students from high-challenge schools but had little effect on enrollment unless institutions also adjusted financial aid — and specifically found that socioeconomic-based practices are a poor proxy for race.

### 3.3 What this means for the project

Three things follow.

First, **the single-score lesson is directly applicable.** The 2019 backlash was specifically about collapsing multidimensional context into one number. This project's deliverable is a five-tier ordinal rigor classification — a single number by another name. The literature does not say don't do it; it says that if you do, the constituent indicators must remain visible and the tier must not be presented as a summary judgment about a school or its students. The project's own commitment to auditability and match-tier metadata (§3.3) is the right instinct and should extend to the rigor score: every tier assignment should be decomposable into the features that produced it.

Second, **the project's risk register is missing a risk.** §2.8 states that "no government approval, socio-cultural, or gender-related considerations apply, given the project's internal, academic, non-commercial scope." The Landscape history demonstrates that a race-neutral, publicly-sourced school context tool built by a nonprofit and used by admissions offices attracted sustained legal and political attention and was ultimately withdrawn. Whether or not one thinks that outcome was justified, an honest risk register should note that a Northwestern-operated equivalent inherits the same exposure, and that the project's "gap detection" deliverable — identifying schools for expanded outreach — is functionally geographic recruiting, the practice named in the DOJ memo. This is a matter for Bob and for Northwestern's counsel, not for the capstone team to resolve, but it should be surfaced to the client rather than asserted away.

Third, **there is now a vacuum.** With Landscape gone, institutions must build their own contextualization or go without. Mabel's assessment — that without clarification, colleges "will revert back to practices that tend to privilege students already coming from more privileged backgrounds" — is as close as this literature comes to a statement of why an in-house, transparent, publicly-sourced platform is worth building. The paper should make this argument.

---

## 4. Measuring School Quality: What the Composite-Indicator Literature Warns

### 4.1 Rankings built on levels measure demographics

The Stanford Education Data Archive (SEDA), launched in 2016, assembled roughly 350 million standardized test scores from every U.S. public school district for grades 3–8 onto a common scale — the closest existing analogue to this project's ambition, and a useful methodological reference (Ho, 2020). Reardon's core finding from SEDA is that average achievement *levels* are powerfully predicted by district socioeconomic composition, while academic *growth* rates from grade 3 to grade 8 bear very little relationship to third-grade scores or to early-childhood advantage. His conclusion — that growth is "a much better measure of school quality" — carries a corollary he states directly: test scores are shaped by home environment, neighborhood, preschool, and out-of-school experience as much as by schooling, and the data "should not be used to rank school districts whose performance differs only slightly."

**Implication.** A five-tier ranking built from levels-type indicators (AP offerings, assessment levels, funding) will substantially reproduce the socioeconomic ordering of American high schools. If the goal is to identify schools where Northwestern should recruit, that ordering may be actively counterproductive — it will rank affluent suburban schools highest and under-resourced schools lowest, which is the opposite of what the gap-detection deliverable is for. This tension between the *rigor tier* (which rewards resources) and *gap detection* (which seeks under-served schools) is unresolved in the current plan and should be addressed in the Methods section.

Note also that SEDA covers grades 3–8 only, so it cannot supply high-school achievement directly. It can, however, supply *feeder-district* academic context for high schools — a genuinely useful and currently unused enrichment source.

### 4.2 Weights do not mean what you think they mean

Two lines of work bear on the mechanics of constructing the tier. First, when a composite is built as a weighted sum of correlated indicators, the *nominal* weights assigned by the designer diverge from the *effective* weights — the actual influence each indicator exerts on the composite, which depends on indicator variances and covariances. A 2024 demonstration using Colorado's School Performance Framework shows that this divergence can materially undermine the validity of interpretations drawn from the composite score (Center for Assessment, Design, Research and Evaluation, 2024). Since this project's rigor features (AP counts, IB flags, per-pupil funding, poverty) are strongly intercorrelated, effective weights should be computed and reported alongside nominal ones.

Second, the broader composite-indicator literature holds that an index without sensitivity analysis can be constructed to support nearly any conclusion; robustness of the tier assignments to alternative weightings should be tested (varying weights, checking rank-order correlation and how many schools change tier). This is a cheap addition to the Week 7 validation phase and would substantially strengthen the "objective and reproducible" claim the project makes to Bob.

### 4.3 The funding overlay

The project's per-student funding overlay draws on Census F-33 and SAIPE. Jackson, Johnson, and Persico (2016) — Jackson is at Northwestern — provide the strongest causal evidence that this variable matters: using court-mandated school finance reforms as exogenous shocks, they find a 10% increase in per-pupil spending sustained across twelve years of schooling raises completed education by 0.27 years, wages by 7.25%, and cuts adult poverty incidence by 3.67 percentage points, with much larger effects for low-income children. Their result is the answer to the Coleman Report's long-standing skepticism about whether money matters.

Two caveats for this project. The finding is about spending *changes over time* identified through policy shocks, not about cross-sectional spending *levels* predicting current school quality — the latter is exactly the confounded comparison Jackson et al. designed around. And the project's data are district-grain (F-33, SAIPE join on LEAID), which the team has already learned the hard way produces join fanout when applied at school grain. The overlay is worth having as descriptive context; it should not be read as a causal input to rigor.

---

## 5. Record Linkage Without a Shared Identifier

### 5.1 The theory the pipeline is already implementing

Fellegi and Sunter (1969) formalized probabilistic record linkage, building on Newcombe's 1959 foundations. Their model compares record pairs on multiple quasi-identifiers, computes a likelihood ratio, and applies **two thresholds** producing a **three-way decision**: link, possible link (referred to clerical review), and non-link. They proved that this rule minimizes the size of the indeterminate middle set for specified false-positive and false-negative rates.

**The project's `auto-accept / review / reject` tiering is a Fellegi–Sunter decision rule.** This should be stated explicitly in the paper — it converts what currently reads as an engineering convenience into a design grounded in fifty-six years of statistical theory, and it gives the team the vocabulary ("clerical review") for the manual review gate in §4.4 of the testing plan. It also identifies a precise limitation: Fellegi–Sunter's optimality result assumes the comparison attributes are conditionally independent given match status, an assumption known to be violated in practice, and the classical algorithm is equivalent to naive Bayes in this respect.

The natural extension, if time permits, is a properly probabilistic implementation — Enamorado, Fifield, and Imai (2019, *APSR*) present an EM-based Fellegi–Sunter model for large administrative merges with an accompanying open-source implementation, and Christen (2012) is the standard reference text for the field. A probabilistic model would let the team report calibrated match probabilities rather than uncalibrated similarity scores, which is a meaningfully stronger claim to make to a client.

### 5.2 Why token ratios are the right choice, and where they fail

Cohen, Ravikumar, and Fienberg (2003) benchmarked edit-distance metrics, heuristic string comparators (Jaro, Jaro-Winkler), token-based metrics, and hybrids on entity name-matching tasks. Their finding: token-based and hybrid methods outperform pure edit distance for entity names, with a hybrid of TF-IDF weighting and Jaro-Winkler performing best overall.

This validates the choice of `rapidfuzz` token ratios over Levenshtein for school names, where word reordering and abbreviation are the dominant error modes. It also predicts exactly the failure the team observed. `token_set_ratio` computes similarity over the *set intersection* of tokens, so a short name that is a strict subset of a long one scores 100 — which is why "Academy High" scores a perfect 100 against a much longer school name while collapsing to ~36 on `token_sort_ratio`. The two-signal guard the team built is a sound, if ad hoc, correction: `token_sort_ratio` reintroduces the length and ordering sensitivity that `token_set_ratio` discards. The paper should present this as a deliberate design response to a documented property of set-based token metrics, with the Academy High and Christ the King cases as evidence, rather than as an empirical accident.

The literature also suggests a cheap improvement: **TF-IDF token weighting**. "High," "School," and "Academy" appear in a large fraction of school names and carry almost no discriminating information; "Wolcott" and "Rosary" carry nearly all of it. Unweighted token ratios treat them identically. Down-weighting high-frequency tokens is the single change most likely to widen the auto-accept tier without admitting false positives — relevant given that only 2 of 77 Illinois private schools currently clear the bar.

### 5.3 The CEEB↔NCES crosswalk is a known, unsolved problem

The project is not the first to encounter this. The University of Colorado Boulder's Office of Data Analytics maintains an open-source `ceeb_nces_crosswalk` repository, explicitly motivated by the "well-known crosswalk problem" and by the observation that prior fuzzy-matching approaches "are helpful, but incomplete." Their method is a three-stage pipeline: (1) ingest the existing Davenport crosswalk from UNC-Greensboro's Institutional Research office, (2) fuzzy-match the remainder, and (3) route unresolved cases to **Amazon Mechanical Turk**, with each school covered by 3–4 independent crowdworkers and discrepancies resolved by tie-breaking aggregation. The published file contains 21,592 matched U.S. secondary schools. Brock Tibert has separately organized a community school-code crosswalk for postsecondary institutions.

Three observations. First, the project's reported 48% auto-accept rate on public high schools against the CU Boulder reference is not anomalous — it reflects that even the reference crosswalk is a partial, crowd-augmented artifact rather than ground truth, and match rates against it should be described as *agreement*, not accuracy. Second, CU Boulder's use of redundant human coders with tie-breaking is a stronger clerical-review design than single-reviewer sign-off, and is worth proposing to Bob for the review tier. Third, the CU Boulder repository accepts contributions; publishing this project's validated matches back upstream would be a concrete, zero-cost contribution to the field and a strong closing note for the paper.

---

## 6. Reproducibility and Pipeline Engineering

The containerization decision has direct support. Boettiger (2015) catalogues why computational work fails to reproduce — dependency drift, undocumented environment state, "code rot" — and argues that Docker addresses these through OS-level virtualization, portable images, and versioned, human-readable Dockerfiles that let a subsequent user reconstruct the original environment. Wiebels and Moreau (2021) extend this into a practical tutorial and note that containers support reproducibility not only after a project concludes but during it, by ensuring that collaborators' environments are identical.

This maps precisely onto the project's stated stakeholder need: a pipeline Bob's team can re-run annually without engineering support. The `docker compose up --build` requirement, the byte-for-byte cross-machine test in §4.3, and the under-two-minute rebuild target are all defensible against this literature. The one gap is that Boettiger's argument is about *environment* reproducibility; the project's stated risk of "data-source schema instability" is *data* reproducibility, a distinct problem that Docker does not solve. Schema-aware validation, pinned source-year snapshots, and the row-count assertions already specified in §4.2 are the correct response, and the paper should distinguish the two clearly rather than letting Docker carry both claims.

---

## 7. Synthesis: What the Literature Supports, and Where It Pushes Back

**Well-supported by the literature:**
- Curriculum intensity as the right construct to measure for predicting college success (Adelman, 1999, 2006).
- School-context data as an intervention that measurably improves both equity and predictive accuracy in admissions (Bastedo et al., 2022, 2023).
- A three-tier accept/review/reject linkage decision under two thresholds (Fellegi & Sunter, 1969).
- Token-based over edit-distance string similarity for entity names (Cohen et al., 2003).
- Containerization as the mechanism for a non-engineer-maintainable annual pipeline (Boettiger, 2015).
- Per-pupil spending as a variable with real causal purchase on student outcomes (Jackson, Johnson, & Persico, 2016).

**Where the literature pushes back:**
- Course *availability* is a weak predictor of college outcomes; exam *performance* is a strong one (Geiser & Santelices, 2004). The model is built mostly on the former. The tier should be named and described accordingly.
- Offering counts are confounded with school size and poverty (GAO, 2018; Kolluri, 2018), which makes the funding/poverty overlay collinear with the rigor target rather than independent of it.
- Levels-based composites reproduce the socioeconomic ordering of schools and should not be used to rank schools that differ only slightly (Reardon; Ho, 2020). This is in direct tension with the gap-detection deliverable.
- Nominal weights are not effective weights when indicators are correlated (CADRE, 2024); sensitivity analysis is required before a five-tier assignment can be called objective.
- A single composite context score has already been tried publicly and withdrawn under criticism (Environmental Context Dashboard, 2019); the successor tool was itself discontinued under legal and political pressure (Landscape, 2025). The project's assertion that no socio-cultural or governmental considerations apply is not supportable.

**Unused sources the literature points to:**
- **CRDC** (school-level, NCES-keyed, universe-level AP/IB/dual-enrollment/SAT-ACT participation) — likely the single highest-value addition available.
- **SEDA** (grades 3–8, district-grain) as feeder academic context.
- **TF-IDF token weighting** as a low-cost matcher improvement.
- **The CU Boulder crosswalk repository** as both a validation reference and a contribution target.

---

## References

Adelman, C. (1999). *Answers in the tool box: Academic intensity, attendance patterns, and bachelor's degree attainment*. U.S. Department of Education. ERIC ED431363.

Adelman, C. (2006). *The toolbox revisited: Paths to degree completion from high school through college*. U.S. Department of Education, Office of Vocational and Adult Education. ERIC ED490195.

Bastedo, M. N., Bell, D., Howell, J. S., Hsu, J., Hurwitz, M., Perfetto, G., & Welch, M. (2022). Admitting students in context: Field experiments on information dashboards in college admissions. *The Journal of Higher Education, 93*(3), 327–374. https://doi.org/10.1080/00221546.2021.1971488

Bastedo, M. N., Umbricht, M., Bausch, E., Byun, B.-K., & Bai, Y. (2023). Contextualized high school performance: Evidence to inform equitable holistic, test-optional, and test-free admissions policies. *AERA Open*. https://doi.org/10.1177/23328584231197413

Boettiger, C. (2015). An introduction to Docker for reproducible research. *ACM SIGOPS Operating Systems Review, 49*(1), 71–79. https://doi.org/10.1145/2723872.2723882

Camara, W., & Michaelides, M. (2005). *AP® use in admissions: A response to Geiser and Santelices*. College Board Research Note. ERIC ED561051.

Center for Assessment, Design, Research and Evaluation. (2024). *Nominal and effective weights of composite accountability ratings: A demonstration using Colorado's School Performance Framework*. University of Colorado Boulder.

Christen, P. (2012). *Data matching: Concepts and techniques for record linkage, entity resolution, and duplicate detection*. Springer.

Coca, V., Johnson, D., & Kelley-Kemple, T. (2012). *Working to my potential: The postsecondary experiences of CPS students in the International Baccalaureate Diploma Programme*. University of Chicago Consortium on Chicago School Research.

Cohen, W. W., Ravikumar, P., & Fienberg, S. E. (2003). A comparison of string distance metrics for name-matching tasks. In *Proceedings of the IJCAI-2003 Workshop on Information Integration on the Web (IIWeb-03)*, 73–78.

Enamorado, T., Fifield, B., & Imai, K. (2019). Using a probabilistic model to assist merging of large-scale administrative records. *American Political Science Review, 113*(2), 353–371.

Fellegi, I. P., & Sunter, A. B. (1969). A theory for record linkage. *Journal of the American Statistical Association, 64*(328), 1183–1210.

Geiser, S., & Santelices, V. (2004). *The role of Advanced Placement and honors courses in college admissions*. Center for Studies in Higher Education, University of California, Berkeley. Research & Occasional Paper Series, ROP.9.04.

Ho, A. D. (2020). What is the Stanford Education Data Archive teaching us about national educational achievement? *AERA Open*. https://doi.org/10.1177/2332858420939848

Jackson, C. K., Johnson, R. C., & Persico, C. (2016). The effects of school spending on educational and economic outcomes: Evidence from school finance reforms. *The Quarterly Journal of Economics, 131*(1), 157–218. https://doi.org/10.1093/qje/qjv036

Jang, H., & Reardon, S. F. (2019). States as sites of educational (in)equality: State contexts and the socioeconomic achievement gradient. *AERA Open*. https://doi.org/10.1177/2332858419872459

Kolluri, S. (2018). Advanced Placement: The dual challenge of equal access and effectiveness. *Review of Educational Research, 88*(5), 671–711. https://doi.org/10.3102/0034654318787268

U.S. Department of Education, Office for Civil Rights. (n.d.). *Civil Rights Data Collection*. https://civilrightsdata.ed.gov

U.S. Government Accountability Office. (2018). *K–12 education: Public high schools with more students in poverty and smaller schools provide fewer academic offerings to prepare for college* (GAO-19-8).

University of Colorado Boulder, Office of Data Analytics. (n.d.). *ceeb_nces_crosswalk* [Software repository]. https://github.com/UCBoulder/ceeb_nces_crosswalk

Wiebels, K., & Moreau, D. (2021). Leveraging containers for reproducible psychological research. *Advances in Methods and Practices in Psychological Science*. https://doi.org/10.1177/25152459211017853

