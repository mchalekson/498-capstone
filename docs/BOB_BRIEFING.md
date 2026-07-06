# The database, for Bob

## What it is

A Postgres database (run via `docker-compose up`) built by an ETL pipeline
(`etl/run_all.py`) in three stages:

1. **Raw** — one table per source, loaded as-is: NCES public/private schools,
   Census school finance (F-33) and SAIPE poverty, NAEP, ISBE report card
   (9 sheets), IB, CPS Opportunity Index, College Board AP.
2. **Clean** — typed/parsed versions (`*_clean`): numeric casts, sentinel
   values (`-1`) converted to null.
3. **Combined** — school-level backbone tables that join everything
   together: `public_schools_enriched`, `private_schools_enriched`, plus
   crosswalks (`ib_nces_crosswalk`, `cps_nces_crosswalk`) and views
   (`illinois_schools_enriched`, `districts_enriched`).

**Don't want to run Docker?** Every table and view is already exported to
CSV in `csv_exports/` — open `public_schools_enriched.csv` or
`private_schools_enriched.csv` directly.

## The ID situation — what's solid vs. what's guessed

| Sources | Join today | Confidence |
|---|---|---|
| NCES private ↔ ELSI private | `PSS_SCHOOL_ID` = `ncessch` (same NCES ID system) | **Solid** — 72% direct match |
| Census F-33 ↔ SAIPE poverty | `LEAID` | **Solid** |
| NCES public schools ↔ district finance | via `leaid` | **Broken today** — see below, has a fix |
| IB, ISBE, CPS ↔ everything else | fuzzy name/city matching, confidence-tiered (`auto_accept`/`review`/`reject`) | **Best-effort**, has a path to solid — see below |

## Three concrete asks, in order of what unblocks the most

### 1. The updated "NU master" CEEB list
IB, ISBE, and CPS have no NCES ID at all in their raw data — only fuzzy name
matching connects them today. The intended fix, per the original EDA
(`EDA.md`) and a teammate's `crosswalk_matcher.py`, is a **CEEB-anchored
master list of ~40k high schools**: match IB/ISBE/CPS to it once, and every
source becomes joinable through one shared ID (CEEB) instead of three
separate guesses.

Bob has a previous copy of this file, but flagged it as stale. **The
pipeline is already wired to consume it the moment a current version shows
up** — see `data/NU-Master/README.md` for the exact file format expected.
Drop it in `data/NU-Master/nu_master.csv`, re-run the pipeline (or just
`python etl/build_ceeb_crosswalk.py`), and three new crosswalk tables appear
(`ib_ceeb_crosswalk`, `isbe_ceeb_crosswalk`, `cps_ceeb_crosswalk`), each
flagged with a confidence tier so low-confidence matches get human review
before anyone trusts them.

### 2. Re-pull the NCES public school export with the 12-digit ID
The public-school data (`data/NCES/ELSI_public_school_grades_9-12_only.csv`)
was pulled from NCES's ELSI tool with a column literally labeled `"School ID
(7-digit) – NCES Assigned"`. That's a truncated ID — the real NCES standard
is a 12-digit `NCESSCH` (7-digit district `LEAID` + 5-digit in-district
code). Because we only have the 7-digit version, `etl/views.sql` already
flags that the district-finance join comes back `NULL` for every public
school; we're aggregating to state level as a workaround.

**Fix:** re-pull from https://nces.ed.gov/ccd/elsi/tableGenerator.aspx and
add the **"School ID (12-digit) – NCES Assigned"** field (and/or "Agency ID
(7-digit) – NCES Assigned" for `LEAID` directly) to the export. That turns
the public-school → district link into a real per-school join instead of a
state-level aggregate.

### 3. The College Board institutional-access escalation (Bob's own item)
Right now AP data is only national/state aggregates (`ap_availability`,
`ap_participation`, `ap_performance`) — there's no school-level AP data
until Bob's institutional-access request with College Board comes through.
This sets the national baseline the rigor model is calibrated against in
the meantime.

## Bottom line for Bob

Nothing here is blocked on engineering time — it's blocked on two files
(an updated master list, a re-pulled ELSI export) and one external
process (College Board access) that only Bob can move forward.
