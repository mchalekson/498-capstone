# Initial EDA — External Source Files (Batch 2)

*Covers the data files uploaded to the project area beyond the two already documented (`NCES_private_merged` by colleague; `NU Org Data` separately). Organized by role in the integrated pipeline: **school-level joins → district/county context → state/national context**. The CEEB-anchored NU master + NCES School ID remain the backbone everything attaches to.*

## Inventory & Status

| File(s) | What it is | Grain | Status |
|---|---|---|---|
| `ib_us_1.csv` | IB World Schools (self-collected) | **School** | **New — profiled below** |
| `cps_opportunity_index_SY26.xlsx` | CPS Opportunity Index | **School (Chicago)** | **New — profiled below** |
| `census_school_finances_FY2024_alldistricts.xlsx` | Census School System Finances (F-33) | District | **New — profiled below** |
| `census_saipe_poverty_2024_schooldistricts.xls` | SAIPE child-poverty estimates | District | **New — profiled below** |
| `naep_grade8_*` / `naep_grade12_*` (4) | NAEP scale scores | State / National | **New — profiled below** |
| `collegeboard_ap_{availability,participation,performance}` (3) | College Board AP reports | National / State | **New — profiled below** |
| `ncesdata_*.xls` (4) | Raw PSS private pulls (TX etc.), HTML-as-xls | School | *Already covered* — source pieces of `NCES_private_merged` |
| `ncesprivateschools.csv` | ELSI private universe 2019-20 (~21k rows) | School | *Already referenced* — the enrichment file for the private merge |

Two format traps worth recording for the ETL: the `ncesdata_*.xls` files are **HTML tables** (4 metadata rows, header on row 5), and every NAEP/College Board file has **junk header/footer rows** (real header ~row 9 for NAEP) plus multi-row pivot headers for AP.

---

## School-Level Sources (join to master)

### IB World Schools — `ib_us_1.csv`

- **1,893 schools × 10 columns.** `school_id` (IBO ID) is a clean primary key — 0 duplicates; 25 duplicate names.
- **Programme flags:** PYP 635 · MYP 761 · DP 917 · CP 194 · any-IB 1,887 (6 rows flag no programme — inspect/repair).
- **Only ~934 are high-school-relevant.** DP and CP are the secondary-level programmes; **934 schools offer DP or CP**. The remaining ~950 are PK–8 (PYP/MYP only, e.g. "A. Philip Randolph Elementary"). **Filter to `offers_dp | offers_cp` before joining to the HS master**, or IB will attach to elementary schools that aren't in scope.
- **Language:** overwhelmingly English (1,519) or English+Spanish (303).
- **No CEEB, no NCES ID — only the IBO ID.** As previously flagged, linkage to the master requires **fuzzy name + state/city matching** with manual review of low-confidence pairs. This is the one source with no clean key.
- **Scope note:** confirms IB authorization/offering only — *not* per-school IB exam scores (those aren't published by ibo.org). "IB rigor" must be modeled as a binary/programme-count feature, not a score.

### CPS Opportunity Index — `cps_opportunity_index_SY26.xlsx`

- Multi-sheet workbook: `Overview`, `Metric Descriptions`, `Elementary Schools`, `High Schools`, `Excluded Schools`. Use **`High Schools`** (129 rows × 9 cols).
- Fields: `School ID` (CPS ID), Name, Network, Governance, School Type, Community Area, **Indicator Sum**, **Average Score** (the composite opportunity metrics).
- **Chicago-only, 129 high schools** — narrow but useful as an equity/opportunity overlay for the IL pilot. The `Metric Descriptions` sheet documents the underlying indicators (disability %, EL %, teacher retention, Simpson diversity, community poverty/uninsured/hardship/life-expectancy).
- **Join path:** CPS `School ID` → embedded in ISBE RCDTS → name/city match to NCES → CEEB. Two hops; small enough to validate by hand.

---

## District / County Context (per-student funding)

### Census School System Finances (F-33) — `census_school_finances_FY2024_alldistricts.xlsx`

- Sheet `elsec24`: **14,077 districts × 183 columns** (a `summary` workbook with 20 pre-tabulated state tables also exists for reference).
- **`NCESID` = 7-digit LEAID, present for 100% of rows → clean district join key.** `UNIT_TYPE` is mostly 5 (independent school districts: 12,892); also dependent/other types.
- Core fields for the funding objective: `V33` (enrollment/membership), `TOTALREV`, `TOTALEXP`, `TCURELSC` (total current spending). **Amounts are in thousands of dollars** — multiply by 1,000.
- **Per-pupil current spending** (`TCURELSC×1000 / V33`): median **$16,840**, mean $20,602, p10 $12,241, p90 $29,279 — right-skewed, as expected.
- **Merge:** private schools have no district, so per-pupil funding attaches to **public** schools via LEAID, and serves as **county-level economic context** (`CONUM`) for private schools.

### SAIPE Child Poverty — `census_saipe_poverty_2024_schooldistricts.xls`

- **13,132 districts × 7 columns.** Fields: `rpopall_24` (total pop), `state`+`distid` (→ LEAID), `name`, `STABREV`, `saepov5_17rv_24` (# children 5–17 in poverty), `rpop5_17v_24` (total children 5–17).
- **Child-poverty rate** (`saepov5_17rv / rpop5_17v`): median **12.5%**, p10 4.5%, p90 25.3%.
- **Join:** reconstruct LEAID as `zfill(state,2)+zfill(distid,5)`. Tested against the finance file: **13,017 LEAIDs overlap** — SAIPE and F-33 align cleanly at the district level, giving a combined funding+poverty district table.

---

## State / National Context (aggregates — no school join)

### NAEP — `naep_grade8_*` (by state) & `naep_grade12_*` (national)

- Real header on row 9: `Year · Jurisdiction · All students · Average scale score`.
- **Grade 8 math & reading are reported by state** (~53 jurisdictions incl. DC, DoDEA, national); **grade 12 math & reading are national-only** (NAEP doesn't publish grade-12 by state).
- 2024 national anchors: G8 math 273.8, G8 reading 258.0, G12 math 146.9, G12 reading 282.6.
- **Merge:** state-level context only — attach G8 by-state figures to schools via state (`PSS_STABB` / NU `Region`). Grade 12 is a single national benchmark row, not a join.

### College Board AP — `availability / participation / performance`

- All three are **national/state aggregate pivot tables** with multi-row headers (broken out by year 2015–2025 and by race/ethnicity) — **not school-level**.
  - *Availability:* # / % of public HS offering ≥5 and ≥10 AP courses (2024-25: 10,112 schools; ~47% offer ≥5).
  - *Participation:* % of HS students taking AP (national 2025 ≈ 22%), with race/ethnicity splits.
  - *Performance:* national AP exam score (5→1) count distributions by year.
- **Merge:** context/benchmark only — attach as national (and where present, race-segmented) reference values. School-level AP still depends on the College Board institutional-access request (Bob's escalation); until then these aggregates set the national baseline the rigor model is calibrated against.

---

## Already-Covered Sources (recorded for completeness)

- **`ncesdata_*.xls` (4)** — raw **PSS private** ELSI pulls (e.g., Texas: San Antonio/Houston/Dallas). HTML-as-xls, 4 metadata rows + header row 5. These are the state pieces already consolidated into `NCES_private_merged` (colleague's EDA). No separate analysis needed.
- **`ncesprivateschools.csv`** — the ELSI **private universe 2019-20** (~21k rows, incl. preschools/childcare, so it is *not* HS-filtered). 6 metadata rows precede the real header (row 7); it parses as one column only if the metadata isn't skipped. This is the enrichment source behind the colleague's 977/1,354 direct-join match — parse with `skiprows=6` and standard quoting.

---

## Integration Summary — keys by source

| Source | Join key | Attaches to | Grain match |
|---|---|---|---|
| IB | **fuzzy name+state** (only IBO ID otherwise) | master via CEEB | school |
| CPS Opportunity | CPS ID → RCDTS → name-match | IL schools | school (Chicago) |
| Census F-33 finances | **LEAID (`NCESID`)** | public schools; county context for private | district |
| SAIPE poverty | **LEAID** (state+distid) | same as F-33 | district |
| NAEP G8 | **state** | all schools (context) | state |
| NAEP G12 / AP reports | national (± race) | benchmark only | national |

Backbone unchanged: **NU master (CEEB, 40k HS) → NCES School ID via fuzzy match → district overlays (F-33 + SAIPE via LEAID) → state overlays (NAEP G8, AP) → IB flag via name match.** The only school-level source lacking a hard key is IB.

## Cleaning To-Dos

1. **IB:** ~~filter to `offers_dp | offers_cp` (934 HS) before matching~~ — done, `combine_schools.py` now filters to DP/CP before the private-school fuzzy match. ~~repair the 6 rows with `offers_any_ib=True` but no programme~~ — re-checked against the current `ib_us.csv`: 0 such rows exist today, nothing to repair. Fuzzy name+state matcher (rapidfuzz) with a manual-review queue — done, see `crosswalk_matcher.py` / `combine_schools.fuzzy_match`.
2. **Finance:** cast `V33`/`TCURELSC` numeric; ×1,000 for dollars; compute per-pupil; keep `UNIT_TYPE==5` for standard districts; pre-join SAIPE on LEAID into one district funding+poverty table.
3. **SAIPE:** build LEAID via zero-padding; derive `child_poverty_rate`.
4. **NAEP:** strip rows 0–8 and the 2 footer rows; keep `Jurisdiction`+`Average scale score`; pivot the four files into one state table (G8 math, G8 reading) + a national benchmark row (G12).
5. **AP reports:** flatten the multi-row pivot headers into tidy (metric, year, race, value); treat as national/state context, not a school join.
6. **ncesprivateschools.csv:** re-parse with `skiprows=6`; filter to HS grade span before use.
7. **Format guards for ETL:** detect HTML-as-xls (`ncesdata_*`) and junk-header offsets (NAEP/AP) automatically so annual re-pulls don't silently break.
