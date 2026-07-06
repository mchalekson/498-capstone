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

## Two things only Bob can unblock, one thing that's on us

### 1. Bob's NU Admissions school list (the "NU master") — genuinely needs Bob, not just a nice-to-have
IB, ISBE, and CPS have no NCES ID at all in their raw data — only fuzzy name
matching connects them today. The intended fix, per the original EDA
(`EDA.md`) and a teammate's `crosswalk_matcher.py`, is to match everything
to a single **CEEB-anchored master list**, so every source becomes joinable
through one shared ID instead of separate guesses.

We looked into whether we could source CEEB codes ourselves instead of
waiting on Bob, the same way we self-sourced NCES/Census/NAEP/IB/ISBE. We
can't: College Board has no bulk export of K-12 school CEEB codes — only a
one-at-a-time search tool (school name + state → single code). CEEB codes
aren't published centrally at all; each college accumulates its own list
over years of applications. That means NU Admissions' own ~45,000-school
recruiting list — even Bob's outdated copy — is the only real bulk source
of CEEB codes available to us. It's also literally the "existing dataset"
the proposal's own **Gap Detection** deliverable is meant to diff against,
so we need it either way.

**The pipeline is already wired to consume it the moment a current version
shows up** — see `data/NU-Master/README.md` for the exact file format
expected. Drop it in `data/NU-Master/nu_master.csv`, re-run the pipeline (or
just `python etl/build_ceeb_crosswalk.py`), and three new crosswalk tables
appear (`ib_ceeb_crosswalk`, `isbe_ceeb_crosswalk`, `cps_ceeb_crosswalk`),
each flagged with a confidence tier so low-confidence matches get human
review before anyone trusts them.

Note: this covers IB/ISBE/CPS ↔ CEEB. The core **NCES ↔ CEEB junction**
itself (the proposal's #2 deliverable, Qifan's RACI item) still needs to be
built the same way once the file arrives — that piece hasn't been coded yet.

### 2. The College Board institutional-access escalation (Bob's own item)
Right now AP data is only national/state aggregates (`ap_availability`,
`ap_participation`, `ap_performance`) — there's no school-level AP data
until Bob's institutional-access request with College Board comes through.
This is already risk #1 in the proposal's own risk log, not a new ask.

### 3. Re-pull the NCES public school export with the 12-digit ID — ours to fix, not Bob's
The public-school data (`data/NCES/ELSI_public_school_grades_9-12_only.csv`)
was pulled from NCES's ELSI tool with a column literally labeled `"School ID
(7-digit) – NCES Assigned"`. That's a truncated ID — the real NCES standard
is a 12-digit `NCESSCH` (7-digit district `LEAID` + 5-digit in-district
code). Because we only have the 7-digit version, `etl/views.sql` already
flags that the district-finance join comes back `NULL` for every public
school; we're aggregating to state level as a workaround.

**Fix:** re-pull from https://nces.ed.gov/ccd/elsi/tableGenerator.aspx and
add the **"School ID (12-digit) – NCES Assigned"** field (and/or "Agency ID
(7-digit) – NCES Assigned" for `LEAID` directly) to the export. Per the
RACI, "master database & data pulls" is Max/Qifan's workstream — this is
just a to-do, not something to bring to Bob.

## Bottom line for Bob

Two things are on you: a current copy of NU's school list, and the College
Board access escalation you're already chasing. The ELSI re-pull is on us
and doesn't need your time.
