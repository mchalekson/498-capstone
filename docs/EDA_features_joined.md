## Update 2026-07-17 — LEAID fix, Goal 4 funding built, private-HS sector bug fixed

Four things changed since the pass below; **the coverage numbers in §1 and the
"missing features" in §4 are now stale** for these specific items (left as-is
below for the historical record, corrected here):

1. **LEAID was wrong, not just "not built yet."** The `leaid` column that ships
   in `schools_org_all` is 5 characters and has a **0% match rate** against
   `census_school_finances_clean.leaid`. The standard LEAID is the first 7
   characters of the 12-digit NCESSCH (`nces_id_12[:7]`); that gets an **87%
   match rate**, verified directly against the finance table. This is the same
   kind of stale truncation `views.sql` already flags for the old
   `nces_public_schools_clean` table — it predates the 12-digit ELSI re-pull.
2. **Goal 4 (funding) is built.** `build_features.py` now joins Census F-33
   (`census_school_finances_clean`) and SAIPE (`census_saipe_poverty_clean`) via
   the corrected LEAID. Public-HS funding coverage: **2.8% -> 66.0%.**
   **Caveat, and it's a real one:** F-33 has no enrollment/membership field,
   and there's no verified district-level enrollment source loaded in this
   pipeline to divide by (the old `nces_public_schools_clean.leaid` has the
   same truncation problem, so it can't be used to aggregate school-level
   enrollment up to district). So the new `per_resident_child_funding_*`
   fields are total/state-local revenue ÷ **SAIPE school-age (5-17) population**
   — a standard Census companion pairing, but a **proxy for enrollment, not an
   actual per-pupil headcount.** Only the IL ISBE `per_pupil_state_local`
   field is true per-pupil expenditure. `funding_source` records which one
   populated each row so the two are never silently averaged together.
3. **The "IB flags didn't land" finding in §4 was a sector-classification bug,
   not a bad match.** All 1,354 `ib_school_id` matches are on rows with
   `pss_id` populated (private schools with a school-side record) and
   `school_level = NaN` (that field is public-only by construction in Sheng's
   export). `is_private_hs` required `school_id` to be null, which excluded
   every one of these rows into `other/oos` — invisible to every coverage
   check. Fixed to `(nu_type private) | pss_id.notna()`. Also: `ib_flag` is
   now `ib_flag_candidate`, gated on `ib_match_tier == 'review'` — nationwide
   IB name-matching has no state to block on, so nothing is ever
   `auto_accept`; the old `ib_school_id.notna()` check was silently counting
   766 `reject`-tier (not just 588 `review`-tier) rows as confirmed IB flags.
4. **`has_nu_data` added** (`nu_guid.notna()`) as the broad "matched any NU org
   record" stratum, separate from `has_nu_analytics` (AP/SAT presence
   specifically).

**Still open, not touched in this pass** — needs either DB access to rerun
`combine_schools.py` or a team call on methodology, not a build-features-layer
fix:
- §3b CEEB fan-out (2,072 duplicate org rows) — confirmed still present,
  unchanged.
- True district enrollment for Goal 4 (would replace the SAIPE proxy above
  with a real per-pupil number) — needs a CCD district membership file, not
  currently loaded.

`etl/build_modeling_dataset.py` is new: takes `build_features.py`'s output,
applies the cleaning freeze (min-size >= 30 grades 9-12, restricts to the
public+private HS universe, sentinel scrub, winsorize sanity check), and
writes a versioned `modeling_dataset_<version>_<date>.csv` +
`data_dictionary_modeling_dataset.csv`.

---

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
4. `combine_schools.py` dup rows (§3b) still open -- needs DB access to rerun,
   or a call on whether to dedup org-side or resolve 1:1 CEEB on the school
   side first. The IB key issue (§4) turned out to be a sector-classification
   bug in `build_features.py`, not the join itself -- fixed, see update above.
5. Reconciliation rule when CRDC AP and Bob's AP disagree.
6. **New:** OK to ship `per_resident_child_funding_*` (F-33 revenue / SAIPE
   population) as a national Goal 4 proxy, clearly labeled as not true
   per-pupil? Or hold for a real CCD district-membership enrollment source?
