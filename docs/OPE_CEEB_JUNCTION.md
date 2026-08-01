# OPE ↔ CEEB junction (postsecondary)

**Secondary goal:** *"Establish a junction mapping system linking OPE (Office of Postsecondary
Education) identifiers, used for colleges, and CEEB (College Entrance Examination Board) codes."*

## Status

Builder shipped: [`etl/build_ope_ceeb_junction.py`](../etl/build_ope_ceeb_junction.py).
**No junction is materialized yet — it is source-gated.** The builder degrades cleanly (exit 0
with guidance) until a source is supplied, and the dashboard's *Crosswalk & junctions* page shows
the same status.

## Why this one is different from every other crosswalk in the repo

Every existing crosswalk here is anchored on **high schools**, where we already hold the federal
IDs (NCES 7-/12-digit, PSS) and match them to CEEB — see
[`etl/build_ceeb_crosswalk.py`](../etl/build_ceeb_crosswalk.py). **OPE IDs identify colleges
(postsecondary institutions)**, a population that appears in *none* of our school-level sources.
So this junction cannot be derived from what the pipeline already loads; it needs an external
college-level table.

The catch (confirmed by sourcing research): **no single free federal table carries both an OPE ID
and a CEEB code.** Federal college data (College Scorecard, IPEDS) keys on `OPEID` / `UNITID`;
CEEB codes are College Board's own identifiers and are distributed separately. CEEB codes are also
**recycled** when institutions close or merge, so any mapping must keep code reuse visible rather
than assume 1:1.

## How to complete it — two paths

### Path A (direct) — a table that already has both codes
Drop a CSV carrying an OPE ID column and a CEEB column at
`data/OPE-CEEB/ope_ceeb_source.csv` (or pass `--source`), then:

```bash
cd etl && python build_ope_ceeb_junction.py --ope-col OPEID --ceeb-col CEEB --version v1
```

Candidate sources (all carry OPEID/IPEDS/CEEB in one row):
- **PESC / SPEEDE "College Crosswalk Table"** (codeset E1178) — matches college CEEB codes to
  FICE/ACT/standard codes; the standard code ties back to OPE. Free.
- **Community "Higher-Ed School Code Crosswalk Database"** — ~2,900 colleges, converts CEEB↔OPEID.
- **CollegeSource TES** export — collects OPEID, IPEDS, and CEEB code changes annually
  (commercial/licensed).

### Path B (match) — build it ourselves from two half-sources
If only a federal `OPEID` file (College Scorecard / IPEDS: OPEID + name + city + state) and a
separate CEEB **college** list are available, join them by fuzzy name + location — the exact
technique [`build_ceeb_crosswalk.py`](../etl/build_ceeb_crosswalk.py) already uses for high
schools. `build_ope_ceeb_junction.py --mode match` is the wired-in hook for this; it reuses that
matcher once both inputs land.

## Output schema (`ope_ceeb_junction_<ver>_<date>.csv`)

| column | meaning |
|---|---|
| `opeid` | 8-digit OPE ID, zero-padded (text) |
| `ceeb` | 6-digit CEEB, zero-padded (text) |
| `institution_name` | college name (if the source carries one) |
| `ope_maps_to_n_ceeb` / `ceeb_maps_to_n_ope` | fan-out counts — how many codes this one maps to |
| `is_one_to_one` | True only for clean 1:1 pairs; False flags code reuse / mergers |

## Getting a source

Fetching any of the above is a download from an external site, so it needs a green light first —
tell me which path you want and I'll pull it in (Path A is fastest if you can point me at, or
license, one of the crosswalk tables above).

## Sources
- [Higher Ed School Code Crosswalk Database (announcement)](https://www.linkedin.com/pulse/project-announcement-higher-ed-school-code-crosswalk-database-tibert)
- [SPEEDE College Crosswalk Table (codeset E1178)](https://www.sc.edu/codeset/E1178.html)
- [CollegeSource TES institution identifier codes](https://collegesource.com/tes-equivalency-export-gets-new-institution-identifier-codes/)
- [K–12 School (CEEB) Code Search — College Board](https://satsuite.collegeboard.org/k12-educators/tools-resources/k12-school-code-search)
- [Crosswalk between CEEB and NCES codes (community thread)](https://groups.google.com/g/qher/c/JC5KOvzL72g)
