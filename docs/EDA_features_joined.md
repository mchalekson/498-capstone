# EDA & Feature Memo — joined table (`schools_org_all` / `schools_org_enriched`)

Supersedes the earlier raw-export memo. This pass measures the **joined** table
(Sheng's public-school export + Bob's NU org export, on CEEB), which is what the
rigor model will actually run on. Universe for the numbers below is the
**public high-school side**: `school_id` present and `school_level ∈ {High, Secondary}`
→ **24,223 schools**. All figures measured directly from `schools_org_all.csv`.

---

## 1. What the join buys us — and where it stops

The single biggest change from the raw export: **CRDC roughly doubles AP/SAT coverage
for public schools.** On the raw NU file the AP/SAT ceiling was ~31%. Joined:

| feature | coverage (24,223 public HS) | notes |
|---|---|---|
| `crdc_ap_offered` = offers AP (flag) | **56.1%** actually offer / 82% have the flag | availability floor |
| `crdc_ap_enrollment` present | 50.9% | for a per-student rate |
| `nu_avg_num_ap_tests_taken` | 37.9% | Bob's direct measure (Goal 8) |
| **any AP signal (nu ∪ crdc)** | **56.1%** | CRDC adds **4,402** schools beyond nu |
| `crdc_satact_takers` | **83.7%** | SAT/ACT participation (Goal 6) |
| `nu_avg_freshman_sat` | 39.2% | score, but selection-biased (see §3) |
| `grad_rate_2021` (EDFacts SY20-21) | 73.8% | answers a Goal question directly |
| `frl_students` → FRL rate | 75.2% | poverty, national |
| `enrollment_9_12` / `total_enrollment` | 99.3% | Goal 5 pipeline + AP denominators |

So for **public** schools the feature picture is now genuinely strong.

## 2. The hard wall: private schools get nothing from the join

The public-school export is CCD-based and **100% public**. Bob's file has **13,385
private high schools; only 825 (6%) matched a public-school row.** The other ~12,560
private HS sit in the org-only bucket with **no CRDC, no grad rate, no enrollment, no
LEAID, no funding** — school-side fields are null by construction. They carry only
Bob's `nu_*` fields, where present.

This is the real modeling split — not "has analytics vs not," but **public
(CRDC-extendable) vs private (nu-only)**. The rigor model behaves like two different
problems on these two populations. Sheng already flagged private funding as a
structural gap; it's actually the whole public-source feature set, not just funding.
Also worth noting: **7,561 *public* orgs** in Bob's file are unmatched too — candidate
CEEB-join failures or schools missing from the CCD pull, not out-of-scope entities.

## 3. Two data issues that will silently corrupt the model

**3a. The socio indices are need-coded, opposite to their names.** `nu_educational_attainment`,
`nu_family_stability`, `nu_housing_stability`, `nu_median_family_income` are labeled by
plain name in the dictionary but behave as *disadvantage* percentiles. Verified against
external Census dollars, not just internal correlation:

- `nu_median_family_income` vs actual `county_median_hh_income`: **r = −0.60**
- `nu_educational_attainment` vs actual `county_pct_bachelors_plus`: **r = −0.55**

High value = *worse* context. Anyone reading "income = 93" as wealthy gets the sign
backwards. `build_features.py` reverse-codes these (`*_adv`, `socio_need_index`) and the
validation report re-checks the sign on every run. Likely College-Board/Naviance
(Landscape-lineage) fields → also can't be refreshed year-over-year (Landscape
discontinued Sept 2025), a sustainability gap.

**3b. `schools_org_all` has 2,072 duplicate org rows.** The dictionary says no fan-out
was possible because `nu_master.ceeb` is unique — but 46,969 org rows carry only 44,897
unique `nu_guid`. CEEB is **not** unique on the *school* side, so those orgs fanned out
across colliding school rows. Any count or aggregate on the org side is inflated by
~2,072. Worth a fix in `combine_schools.py` (dedup or 1:1 CEEB resolution on the school
side before the join).

## 4. Two features still missing / not built

- **IB flags didn't land.** `ib_school_id` is populated on 1,354 rows, **none of them in
  the High/Secondary universe** (they're on level-null rows). The ~1,900-school IB work
  isn't usable as a feature yet — the IB→school key needs re-checking.
- **National per-pupil funding (Goal 4) isn't joined.** Only IL ISBE per-pupil is present
  (670 schools, 2.8%). But `leaid` is 100% present, so the F-33 ÷ enrollment join Sheng
  described is ready to build — it's a build task, not a data gap.

## 5. Feature decisions (what `build_features.py` produces)

- **Use national, high-coverage:** `grad_rate_2021` (74%), `frl_rate` (75%),
  `enrollment_9_12` + grade bands (99%), `testtaker_rate` (82%), `ap_offered` (82% flag).
- **AP intensity — keep two distinct measures, don't fake-average them:** `ap_tests_taken`
  (nu, avg #tests/student) and `ap_participation` (crdc_ap_enrollment ÷ enrollment,
  winsorized — raw max was 9.5, clearly dirty). Different constructs; `ap_intensity_src`
  records provenance.
- **SAT:** `testtaker_rate` (CRDC, 82%) for participation; `sat_score_nu` (39%) for score,
  labeled selection-biased.
- **Socio:** reverse-coded `*_adv` + `socio_need_index` (higher = more need).
- **Ordinals → midpoints:** the six bucket columns (`Percent going to college` etc.).
- **Strata:** `sector` (public/private/oos), `has_nu_analytics`, `is_school_match`.
- **Drop:** `nu_mean_sat`, `nu_network`, `nu_ccid`, IL-only `act_*`/`iar_*`/`isbe_*`
  (keep for IL validation only), `county_pct_poverty` (redundant with SAIPE, r=0.89).

## 6. Rigor target (Goal 3) — still unlabeled
No 5-tier ground truth anywhere. Options, in order of preference: (a) get historical
manual labels from Bob; (b) weak supervision — anchor tiers to `grad_rate_2021` +
AP/SAT composites where present; (c) unsupervised composite index → tier cut-points.
Whichever, the public/private split (§2) means tiers won't be comparable across sectors
without care.

## 7. Send to Bob / Max / Sheng
1. Historical rigor labels available? (Goal 3)
2. Per-variable vintage for the `nu_*` fields (dictionary confirms: undated).
3. Confirm socio indices are need-coded / Landscape-derived (§3a).
4. Fix `combine_schools.py` dup rows (§3b) and the IB key (§4).
5. Reconciliation rule when CRDC AP and Bob's AP disagree.
