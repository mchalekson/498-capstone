# NU master (CEEB-anchored school list)

This is the missing piece of the ID backbone described in `EDA.md` — the
~40k-high-school list, keyed by CEEB code, that IB / ISBE / CPS Opportunity
Index would otherwise only ever reach via fuzzy name matching.

**Status: not present.** Bob has a previous copy, but flagged it as out of
date and in need of updating. Nothing in this repo currently ships a version
of this file.

## What to drop here

A file named `nu_master.csv` (or `.xlsx`) with, at minimum, these columns
(matching `crosswalk_matcher.py`'s defaults):

| Column | Meaning |
|---|---|
| `Name` | School name |
| `Region` | State — either abbreviation or full name both work; `etl/build_ceeb_crosswalk.py` canonicalizes either |
| `City` | School city (improves match precision; not required) |
| `CEEB` | The CEEB code — this becomes the shared join key |

If the real column names differ, either rename them to match or adjust the
`master_name`/`master_state`/`master_city`/`master_ceeb` arguments passed to
`match_to_master()` in `etl/build_ceeb_crosswalk.py`.

## What happens once it's here

`etl/build_ceeb_crosswalk.py` is already wired into `etl/run_all.py`. The
moment a file exists at this path (or `NU_MASTER_PATH` is pointed elsewhere),
the pipeline will start producing three new tables — `ib_ceeb_crosswalk`,
`isbe_ceeb_crosswalk`, `cps_ceeb_crosswalk` — each with a confidence tier
(`auto_accept` / `review` / `reject` / `no_candidate`) so low-confidence
matches can be reviewed by hand before being trusted. Until then, this step
just prints a skip message and the rest of the pipeline runs unaffected.
