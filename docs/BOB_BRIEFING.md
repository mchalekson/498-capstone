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

## One thing Bob already unblocked, one thing still on him

### 1. Bob's NU Admissions school list (the "NU master") — RESOLVED 2026-07-14
Bob's export (`Capstone Org Data 20260624-093658.xlsx`, ~44,900 orgs) is now
loaded at `data/NU-Master/nu_master.xlsx` — see `data/NU-Master/README.md`
for the full breakdown. This unblocked the three crosswalk tables that were
previously no-ops: `ib_ceeb_crosswalk`, `isbe_ceeb_crosswalk`,
`cps_ceeb_crosswalk` (each confidence-tiered — `ib_ceeb_crosswalk` has 0
auto-accepts by design, see that README). It also enabled a new
`schools_org_enriched` table: a nationwide schools export (already carrying
CEEB via a separate UC Boulder crosswalk — `data/CEEB-Crosswalk/README.md`)
left-joined directly to Bob's org data on CEEB, matching 18,580/25,577
schools (73%).

Note: this covers IB/ISBE/CPS ↔ CEEB. The core **NCES ↔ CEEB junction**
(the proposal's #2 deliverable, Qifan's RACI item) is a separate piece,
already built against the UC Boulder crosswalk in
`etl/build_ceeb_crosswalk.py`'s `build_nces_junction()` —
`nces_public_ceeb_crosswalk` / `nces_private_ceeb_crosswalk`.

### 2. The College Board institutional-access escalation (Bob's own item)
Right now AP data is only national/state aggregates (`ap_availability`,
`ap_participation`, `ap_performance`) — there's no school-level AP data
until Bob's institutional-access request with College Board comes through.
This is already risk #1 in the proposal's own risk log, not a new ask.

### 3. Re-pull the NCES public school export with the 12-digit ID — ours to fix, not Bob's
The public-school data was pulled from NCES's ELSI tool with a column
literally labeled `"School ID (7-digit) – NCES Assigned"`. That's a
truncated ID — the real NCES standard is a 12-digit `NCESSCH` (7-digit
district `LEAID` + 5-digit in-district code). Because we only have the
7-digit version, `etl/views.sql` already flags that the district-finance
join comes back `NULL` for every public school; we're aggregating to state
level as a workaround.

**Still open.** A re-pull with the 12-digit ID was added
(`data/NCES/ELSI_csv_new_updated.csv` → `nces_public_hs_grades_9_12`), but
that's a re-pull of the wrong export — the join that's actually broken
(`illinois_schools_enriched`, `public_schools_enriched`, the CEEB junction)
runs against `nces_public_schools_clean`, built from the much larger
**`data/NCES/nces-public-schools.csv`** (all grade levels, 101k rows), which
still only has the 7-digit ID. `nces_public_hs_grades_9_12` isn't used in
that join at all — see the comment in `etl/build_ceeb_crosswalk.py` on why
(it's missing schools the broader table has, e.g. New Trier).

**Fix:** re-pull `nces-public-schools.csv` itself (not the 9-12-filtered
extract) from https://nces.ed.gov/ccd/elsi/tableGenerator.aspx and add the
**"School ID (12-digit) – NCES Assigned"** field (and/or "Agency ID
(7-digit) – NCES Assigned" for `LEAID` directly) to the export. Per the
RACI, "master database & data pulls" is Max/Qifan's workstream — this is
just a to-do, not something to bring to Bob.

## Bottom line for Bob

The NU school list is in — thanks. One thing still on you: the College
Board access escalation you're already chasing. The ELSI re-pull is on us
and doesn't need your time.
