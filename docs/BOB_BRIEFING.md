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
left-joined directly to Bob's org data on CEEB, matching 16,508/25,577
schools (64.5% — corrected 2026-07-17 after fixing a CEEB fan-out bug that
had inflated this to 18,580/73%; see `docs/DATA_DICTIONARY.md` update).

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

## Update 2026-07-17 — data dictionary is ready for you and Adam to review

Since the meeting: fixed a district-ID bug that was blocking the per-student
funding build (Goal 4), built that funding join, fixed a sector-classification
bug that was hiding IB flags, and fixed the CEEB fan-out bug mentioned above
(match rate corrected 73% -> 64.5% — the original 73% included ~2,072 false
matches from a fuzzy-matching artifact, not real ones). Details in
`docs/EDA_features_joined.md`'s two "Update 2026-07-17" sections if you want
the specifics.

**What's ready for you and Adam to go through now:**
- `docs/DATA_DICTIONARY.md` + `data_dictionary_schools_org_enriched.csv` —
  the raw joined table, 127 variables (source, grain, vintage, confidence,
  description).
- `csv_exports/data_dictionary_modeling_dataset.csv` — the derived/engineered
  feature set (51 variables) actually used for modeling, same schema.
- `csv_exports/modeling_dataset_v1_2026-07-17.csv` — the frozen, versioned
  dataset itself (34,392 rows: public + private HS, min enrollment 30+).

**What we still need from you (or Sheng), in order of how much they're
blocking us:**
1. Per-variable vintage for the 56 `nu_*` fields — right now the dictionary
   can only confirm the export date (2026-06-24), not when each underlying
   stat (mean SAT, AP participation, etc.) was actually measured. This is
   the "old section vs. new section" concern from the meeting — we have the
   column to hold the answer, we don't have the answer.
2. Sign-off on the Goal 4 national funding proxy: is total district revenue
   ÷ SAIPE school-age population an acceptable stand-in for true per-pupil
   spending, or should we hold off until a real district-enrollment source
   is available? (IL's ISBE figure is true per-pupil; this one isn't.)
3. Reconciliation rule for when CRDC's AP data and your AP data disagree.

**What we resolved ourselves instead of waiting** (2026-07-17, second pass):

- ~~Historical rigor labels~~ — not actually needed. The rigor tier is a
  constructed weighted composite (report Section 4.1), not a supervised
  label learned from historical ground truth. See `docs/RIGOR_CLASSIFICATION.md`.
- ~~Confirm the socio-context fields are Landscape-derived/need-coded~~ —
  confirmed ourselves, no need to ask. All 5 fields (`crime_risk`,
  `educational_attainment`, `family_stability`, `housing_stability`,
  `median_family_income`) correlate 0.38-0.91 with each other and share the
  same 1-100 scale, and 2 of the 5 already check out externally against
  Census data (r=-0.60, -0.55). All five move together in the same
  direction, so all five are need-coded the same way, not just the two we
  could check against an outside source.
- ~~Custom ID variable from Org Data~~ — investigated directly instead of
  waiting on you to check your system. `custom_id` (76.5% populated, mostly
  7-digit) doesn't match any federal ID we have (0% match against NCES's
  7-digit school ID) and isn't fully unique (84 duplicate values) — it's an
  internal identifier from whatever system this export came from, not
  something with cross-referencing value here. **But investigating its
  duplicates surfaced something we weren't looking for:** 62 of those 84
  duplicate pairs are two clearly different schools whose CEEB codes are
  related by an exact leading-zero/trailing-zero shift (e.g. `050003` vs.
  `500030`) — the classic signature of a 6-digit zero-padded code getting
  stored as a number somewhere upstream and re-padded on the wrong side.
  Scanning the whole file the same way flags 644 CEEB codes total with a
  same-file counterpart fitting this pattern (some fraction of those are
  probably coincidental, not all bugged — the 62 are the confirmed ones).
  Flagged (not auto-corrected — no reliable way to tell which side of a
  pair is right) via `ceeb_suspected_padding_shift` in
  `etl/load_nu_master.py`, applied to `nu_master_org_data`. Worth a look on
  your end if you know which export step introduces this.

## Bottom line for Bob

The NU school list is in — thanks. The data dictionary you and Adam asked
about is ready to review (see above). Two things still need your input
(per-variable vintage, the funding-proxy sign-off) — rigor labels and the
two data-provenance questions from the meeting turned out to be answerable
from the data itself and didn't need your time after all. One new thing
worth your attention: a likely CEEB formatting bug in your export, affecting
at least 62 confirmed schools (see above) — flagged, not fixed, since we
can't tell which side of each pair is correct without knowing your source
system. The College Board access escalation is still on you, separately.
The ELSI re-pull is on us and doesn't need your time.
