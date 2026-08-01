# OPE ↔ CEEB Crosswalk (Colleges) — Secondary Goal 1

Date: 2026-07-31 · Output: `csv_exports/ope_ceeb_crosswalk_2026-07-31.csv` · Code pattern reuses the high-school matching funnel.

## Inputs

- **CEEB side**: the NU org export's `Category = College` rows — 4,004 U.S. institutions, all with CEEB codes, 99.7% geocoded.
- **OPE side**: IPEDS HD2023 directory (`data/IPEDS/HD2023.csv`) — 6,126 Title-IV institutions with valid OPEID, UNITID, and coordinates.

## Method — the same funnel, college-tuned

1. **Name normalization** built for CEEB/ATP abbreviation style ("U Arkansas CC Hope", "Colg Nrsg", "Theol Sem"): ~30 expansion rules plus a context-sensitive `St` → *State* (before Univ/College) vs. *Saint* disambiguation, tried both ways.
2. **Tiered acceptance**, state-blocked: exact normalized token match → token-subset with same city or geo < 15 km (catches branch-campus naming) → fuzzy ladders backed by geography (≥90 with city/10 km; ≥65 within 3 km; ≥55 within 1 km).
3. **Geographic verification** is first-class: both sides carry coordinates, so weak name evidence is only accepted when the campuses are physically co-located.

## Results

| Outcome | n | Share |
|---|---|---|
| Matched (rules + adjudication) | **2,794** | 69.8% |
| Likely not in IPEDS 2023 (closed / renamed / non-Title-IV) | 1,208 | 30.2% |
| Residual review queue | 1 | <0.1% |
| Distinct OPEIDs mapped | 2,630 | — |

Golden check: Northwestern University → OPEID 00173900 (exact); its School of Professional Studies row maps to the same OPEID via the subset rule — correct, since OPEID is institution-level.

## The 1,208 "not in IPEDS 2023" rows are a finding, not a failure

Sampling shows they are dominated by institutions that no longer exist or no longer operate under that identity: ITT Technical Institute campuses, DeVry/Kaplan/Rasmussen sites (closed or absorbed — Kaplan → Purdue Global), hospital schools of nursing, and small trade schools. The org export retains them; the federal directory of currently operating Title-IV institutions does not. This mirrors the high-school side's finding: **the NU master list carries a historical tail that no longer maps to the live institutional landscape.**

## Adjudication pass (completed 2026-07-31)

All 209 review rows were adjudicated case-by-case: 105 accepted (tier `llm_adjudicated_accept`) — dominated by renamed institutions (College → University: Alvernia, Lesley, Lourdes, Shorter, St. Catherine…), system branch campuses mapped to their institution-level OPEID (Columbia schools, Tarrant/Cuyahoga/San Jacinto campuses, Troy University sites — including cross-state), and CEEB-abbreviation misses (EDP University, NUC, Sagrado Corazon). 103 were reclassified as not in IPEDS 2023 (ITT/Heald/Brown Mackie/Art Institute campuses, closed colleges such as Newbury, Concordia Bronxville, Daniel Webster, hospital nursing schools). One garbled PR record remains in review.

## Remaining work

- Optional: match the defunct tail against a historical IPEDS year (e.g., HD2015) if the client wants closed institutions resolved rather than flagged.

## Bonus

`UNITID` ships alongside OPEID in every matched row — this keys the entire IPEDS universe (admissions rates, tuition, completion), giving the platform a ready-made college-side expansion path.
