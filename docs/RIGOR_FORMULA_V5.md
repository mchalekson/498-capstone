# The v5 Rigor Index — Formal Specification

MSDS 498 Capstone · 31 July 2026 · Code: `etl/build_rigor_v5.py`
Input: `Capstone_Org_Data_extended_v4_full_2026-07-31.xlsx` (49,268 rows)
Supersedes: *The v4 Rigor Index — Formal Specification*, July 2026

---

## 1. What changed and why

v5 keeps v4's four-layer architecture — derived inputs, standardization, component scores, weighted composite with proportional reallocation, Jenks tiering — so the two indices remain directly comparable. Four substantive changes:

**(a) The "CRDC coursework" component is decomposed.** v4 averaged AP participation, dual-enrollment rate and IB intensity into a single component at weight 0.20. Those are three different constructs, and the client asked about dual enrollment specifically. v5 splits them into `advanced_access` (0.10) and `ib` (0.05).

**(b) Three client rigor factors gain components.** v4 had no term for STEM course-taking, college placement, or faculty quality — factors 1, 3 and 4 of the client's six. v5 adds `stem_depth` (0.10), `college_placement` (0.10) and `faculty_investment` (0.05).

**(c) Test participation is re-weighted 0.15 → 0.05.** v4's own variance decomposition measured its effective weight at 0.074, less than half its nominal weight. v5 aligns the nominal weight to the measured contribution and reallocates the difference to the new components.

**(d) A minimum coverage floor is introduced.** See §6. v4 had none, and every extreme score in the v4 index was an artefact of its absence.

---

## 2. Universe definition

Two independent exclusion rules, applied as a union. Neither alone is sufficient:

| Rule | Excludes | Caught only by this rule |
|---|---|---|
| CEEB length = 4 (college code, zero-padded) | 3,781 | 11 |
| Org `Category` = "College" | 4,004 | 234 |
| **Union** | **4,015** | — |

The 234 rows the CEEB rule misses are hospitals, nursing schools and institutes that hold six-character CEEBs (Abington Memorial Hospital, Air Force Institute of Technology, American Musical and Dramatic Academy). The 11 rows the `Category` field misses are secondary schools mis-typed as colleges. Three further rows are test records with malformed CEEBs (7 and 9 characters).

**Universe: 45,250 rows.** Duplicate GUIDs: 0. Duplicate six-character CEEBs: 0. The join fan-out present in earlier exports has been resolved upstream.

Of these, 4,047 rows carry no CEEB. All 4,047 come from the gap list delivered on 2026-07-27 — schools present in the federal roster and absent from the NU master list. They are now in the universe and 96% of that gap list has been absorbed.

---

## 3. Layer 0 — Derived inputs

**AP qualifying density** (carried over from v4, unchanged). With $t_i$ = AP tests taken per student and $\bar{s}_i$ = mean AP exam score:

$$\mathrm{QD}_i = t_i \cdot \Pr(\text{score} \geq 3) = t_i \cdot \Phi\!\left(\frac{\bar{s}_i - 2.5}{1.2}\right)$$

$\Phi$ is the standard normal CDF; 1.2 is the assumed within-school score SD, a documented approximation since the College Board does not publish school-level score distributions. 10,504 values are carried from the export; 5,769 are recomputed here from $t_i$ and $\bar{s}_i$ where the export left the field null but both inputs were present.

**IB intensity** (carried over from v4, unchanged). With $\mathrm{IB}^{enr}_i$ = CRDC IB enrollment, $E_i$ = grade 9–12 enrollment, $F_i \in \{0,1\}$ the verified IB flag:

$$\mathrm{IBint}_i = \begin{cases} \mathrm{IB}^{enr}_i / E_i & \text{if CRDC enrollment available} \\ F_i & \text{otherwise} \end{cases}$$

**Band midpoints** (new in v5). The org export stores college placement, AP class counts, senior class size and lunch aid as text bands. Each is mapped to its interval midpoint; open-ended bands take $0.5\times$ the bound for "*X* or fewer" and $1.05\times$ for "over *X*". The mapping was audited against every distinct raw value present in the export — for example "26% – 50%" → 38.0, "Over 90%" → 94.5, "25% or fewer" → 12.5. Parse rate is 100% of non-null values.

**STEM breadth** (new in v5). $\mathrm{STEM}_i = \sum$ of the four CRDC binary offering flags (calculus, advanced mathematics, chemistry, physics), range 0–4.

All Layer 0 continuous inputs are winsorized at the 1st and 99th percentiles.

---

## 4. Layer 1 — Standardization

Each raw sub-feature $x$ is $z$-scored over all schools reporting it:

$$z(x_i) = \frac{x_i - \mu_x}{\sigma_x}$$

No imputation at any point.

---

## 5. Layer 2 — Component scores

Component score $C_{ik}$ is the mean of the $z$-scored sub-features school $i$ actually reports.

| Component $k$ | Sub-features | Weight $w_k$ | Client factor |
|---|---|---|---|
| AP opportunity | AP tests taken; tests offered; classes offered (band); take rate; Capstone flag | 0.15 | 1 |
| **AP performance** | AP qualifying density QD | **0.20** | 1 |
| Advanced access | AP participation (CRDC); dual-enrollment rate | 0.10 | 1 |
| IB | IB intensity IBint | 0.05 | 1 |
| **STEM depth** | STEM breadth (0–4) | **0.10** | 1 |
| **Test performance** | mean SAT; ACT composite (IL) | **0.20** | 2 |
| Test participation | test-taker rate; SAT participation | 0.05 | 2 |
| **College placement** | % to college; % to four-year (bands) | **0.10** | 3 |
| **Faculty investment** | % teachers certified; instructional spend per pupil | **0.05** | 4 |

Weights sum to 1.000. Grouped by client factor: advanced curriculum 0.60, test scores 0.25, college placement 0.10, faculty 0.05.

Client factors 5 (extracurricular breadth) and 6 (GPA, academic competitions) carry **no component**. No national dataset of high-school club offerings exists, and GPA is neither standardized across schools nor collected federally. These are not deferred items; they cannot be sourced from public data and would have to come from NU's own application records.

---

## 6. Layer 3 — Weighted composite with proportional reallocation

Let $A_i \subseteq \{1,\dots,9\}$ be the components available for school $i$, and $\omega_i = \sum_{k \in A_i} w_k$ the share of index weight present. The rigor score is

$$R_i = \frac{\sum_{k \in A_i} w_k\, C_{ik}}{\omega_i}, \qquad \text{defined only where } \omega_i \geq 0.25$$

**The coverage floor $\omega_i \geq 0.25$ is new in v5**, and it corrects a real defect. Under v4's convention a school reporting only the IB component — nominal weight 0.05 — still received a tier, and its score was a single $z$-score divided by itself. Empirically, single-component schools carried 1.5× the score variance of the full population and produced **every one of the ten scores beyond $|3|$**. Two schools scored on IB alone sat at $R = 7.66$, above every school in the country that reported all nine components. The v4 index has the same pathology: its published maximum is 10.33.

Imposing the floor moves the maximum from **7.66 to 3.33** and eliminates the artefact.

The cost is real and should be stated: **6,167 schools become unscored**, of which 2,644 are private and 804 public. Most were being tiered on a single band-coded field — 3,077 on college placement alone, 1,384 on test participation alone. Reporting those as measured rigor was not defensible; reporting them as insufficient data is.

Schools below the floor, and schools with $A_i = \emptyset$, are logged **unscored** and never defaulted to a middle tier (v4 convention, retained).

**Coverage: 22,869 of 45,250 schools scored (50.5%)** — 17,015 public, 3,250 private.

---

## 7. Layer 4 — Tier assignment

Tiers are cut by Jenks natural breaks, computed as one-dimensional $k$-means on $\{R_i\}$ with $k=5$ and a fixed seed. Centroids are ordered low → high and mapped onto Below Average → Average → Demanding → Very Demanding → Most Demanding.

**Fitted cut-points:** $-0.704$, $-0.207$, $+0.286$, $+0.977$.

| Tier | n |
|---|---|
| Below Average | 2,868 |
| Average | 7,299 |
| Demanding | 7,211 |
| Very Demanding | 4,050 |
| Most Demanding | 1,441 |

An equal-frequency quintile assignment is emitted alongside as the cut-point sensitivity check; the two schemes agree for **58.4%** of scored schools.

A **within-sector** track is emitted in parallel (`rigor_*_v5_sector`): scores are re-standardized and re-tiered inside `public` and `private` separately. This is the "public rigor / private rigor" option. It is not a default — see §10.

---

## 8. Reported diagnostics

### 8.1 Nominal vs. effective weight

Variance decomposition on the 5,604 full-coverage schools:

| Component | Nominal | Effective |
|---|---|---|
| AP opportunity | 0.15 | 0.129 |
| **AP performance** | 0.20 | **0.364** |
| Advanced access | 0.10 | 0.096 |
| IB | 0.05 | 0.017 |
| STEM depth | 0.10 | 0.031 |
| **Test performance** | 0.20 | **0.247** |
| Test participation | 0.05 | 0.015 |
| College placement | 0.10 | 0.079 |
| Faculty investment | 0.05 | 0.022 |

AP performance contributes 0.364 of index variance against a designed 0.20 — v4's central finding reproduces and strengthens. Test participation, now at nominal 0.05, contributes 0.015; the re-weighting in change (c) was correctly directed but could go further.

STEM depth (0.031) and faculty investment (0.022) contribute less than designed. Both are low-variance measures — STEM breadth is a 0–4 integer where 73% of public schools sit at 3 or 4, and teacher certification is at 100% for the median school. They earn their place by covering client factors nothing else addresses, not by discriminating strongly.

### 8.2 Sensitivity to alternate weighting schemes

Reported two ways, because refitting Jenks conflates two different things — schools moving in the score distribution, and the cut-points themselves moving. The frozen-cut-point column isolates score movement.

| Scheme | Spearman ρ | % changed (Jenks refit) | % changed (frozen cuts) |
|---|---|---|---|
| `v4_equivalent` | 0.879 | 43.1% | 32.3% |
| `equal` (1/9 each) | 0.950 | 23.2% | 26.1% |
| `performance_heavy` | 0.959 | 26.0% | 24.3% |
| `no_new_factors` | 0.922 | 43.9% | 24.9% |

The v4-equivalent comparison is the headline: **32.3% of schools change tier on score movement alone**, at ρ = 0.879. The v5 revisions are not cosmetic. That roughly a quarter of schools move under *any* re-weighting is the honest counterpoint — the index is a designed composite, and its tier boundaries carry genuine specification uncertainty.

### 8.3 CRDC-loss scenario

Zeroing the three CRDC-dependent components (advanced access, STEM depth, faculty investment) among the 11,290 schools that currently have CRDC signal: ρ = **0.958**, **40.5%** change tier. v5 is materially less score-sensitive to CRDC loss than v4 (ρ 0.88), because the added NU-sourced components carry more of the index — but the tier assignment remains fragile. CRDC access is still the single largest external dependency.

### 8.4 v4 → v5 migration

Compared on the 17,882 schools tiered by both: ρ = **0.723**, **63.1%** change tier. The magnitude is expected — four of nine components are new or re-scoped, and the coverage floor removes 6,167 schools from the scored set.

### 8.5 Socioeconomic entanglement

$\rho(R, \text{child poverty})$ moves from **−0.168 in v4 to −0.323 in v5**. The increase is concentrated in the performance components:

| Component | ρ vs child poverty |
|---|---|
| Test performance | −0.392 |
| AP performance | −0.391 |
| AP opportunity | −0.230 |
| STEM depth | −0.213 |
| Faculty investment | −0.192 |
| Advanced access | −0.188 |
| College placement | −0.166 |
| IB | −0.047 |
| Test participation | +0.044 |

This is the predicted cost of the literature-motivated shift toward exam performance. It is reported, not hidden, and §9 provides the remedy.

---

## 9. Layer 5 — Opportunity-adjusted rigor (new in v5)

The rigor tier rewards well-resourced schools; the project's gap-detection deliverable targets under-resourced ones. As the index gets better at measuring rigor it gets worse at that second job. v5 resolves this by emitting a second, orthogonal measure rather than compromising the first.

Regress the rigor score on socioeconomic context (district child poverty, free-and-reduced-lunch rate) and retain the residual:

$$\tilde{R}_i = R_i - \hat{R}_i, \qquad \hat{R}_i = \beta_0 + \beta_1 \mathrm{pov}_i + \beta_2 \mathrm{frl}_i$$

Context explains $R^2 = 0.209$ of the score across 19,150 schools. The residual's correlation with poverty is **−0.028**, effectively zero. Schools above the 90th percentile of $\tilde{R}$ are flagged `overperformer_v5`.

This generalizes to the whole index the "low offering, high scores" idea the client raised in Week 5, which v4 applied to AP alone.

**Effect.** The raw tier places 69 high-poverty schools in the top tier. The residual surfaces **343** high-need overperformers, a 5× increase. Named examples pass inspection: Bronx High School of Science, Brooklyn Technical, J. R. Masterman (Philadelphia), Metro High (St. Louis), Eleanor Roosevelt (New York).

The two measures answer different questions and should be labelled as such: $R$ answers *how demanding is this school*; $\tilde{R}$ answers *which schools outperform their circumstances*.

---

## 10. Validation

Tier means against five external measures, four of which are not model inputs:

| Tier | n | Grad rate | Mean SAT | AP score | % to college | STEM breadth | Child poverty |
|---|---|---|---|---|---|---|---|
| Below Average | 2,868 | 69.8 | 1,041 | 1.79 | 35.6 | 1.20 | 18.2 |
| Average | 7,299 | 85.6 | 1,099 | 2.20 | 51.3 | 2.93 | 17.3 |
| Demanding | 7,211 | 89.7 | 1,139 | 2.66 | 64.1 | 3.54 | 14.2 |
| Very Demanding | 4,050 | 92.3 | 1,178 | 3.08 | 74.2 | 3.76 | 12.6 |
| Most Demanding | 1,441 | 95.5 | 1,252 | 3.47 | 85.9 | 3.81 | 12.0 |

Monotone on every column with no inversions. Graduation rate — never a model input — rises 69.8 → 95.5 across the five tiers, correcting the top-tier dip present in earlier revisions.

The child-poverty column is included deliberately: it declines monotonically, which is the §8.5 entanglement made visible rather than argued about.

---

## 11. Known limitations

**Private schools cannot be scored on the same instrument.** Three components — advanced access, STEM depth, faculty investment — are **0.0%** covered for private schools, because CRDC is a public-school collection by statute. A private school is scored on at most six of nine components, and after the coverage floor only 3,250 of 13,229 private schools are tiered at all. The pooled score therefore does not compare like with like. The within-sector track (§7) is the alternative, and it changes the picture substantially: within-sector standardization places 1,270 private and 1,179 public schools in the top tier, against a pooled split that strongly favours public schools with full CRDC coverage.

**This is a client decision, not a modelling one**, and it should be put to the client directly: should a private school be ranked against private peers or against every school in the country? Both outputs ship; neither is set as the default.

**Other standing limitations.** The SD ≈ 1.2 approximation in QD is undocumented by the College Board. Jenks cut-points are relative to the scored population and anchor to no external standard. The index measures institutional opportunity and performance structure, not any individual applicant's coursework — the tier labels retain NU's counselor vocabulary but do not mean the same thing. And no ground-truth rigor labels exist anywhere in this project, so §10 is convergent validation, not accuracy.

---

## 12. Outputs

| File | Contents |
|---|---|
| `rigor_classification_v5_2026-07-31.csv` | Per-school scores, both tier tracks, residuals, component values |
| `Capstone_Org_Data_extended_v5_2026-07-31.xlsx` | Delivery format — export columns plus v5 fields |
| `rigor_v5_weights_2026-07-31.csv` | Nominal vs effective weights |
| `rigor_v5_sensitivity_2026-07-31.csv` | Alternate-scheme table, both tiering conventions |
| `rigor_v5_component_coverage_2026-07-31.csv` | Coverage by component and sector |
| `rigor_v5_ses_entanglement_2026-07-31.csv` | Per-component poverty correlation |
| `rigor_v5_validation_2026-07-31.csv` | Tier means against external measures |
| `rigor_v5_audit_2026-07-31.csv` | Every count in this document |
