# NU master (CEEB-anchored school list)

This is the missing piece of the ID backbone described in `EDA.md` — the
~40k-high-school list, keyed by CEEB code, that IB / ISBE / CPS Opportunity
Index would otherwise only ever reach via fuzzy name matching.

**Status: present.** Bob's export (`nu_master.xlsx`, ~44,900 orgs, one sheet
named "Export") lives at `data/NU-Master/nu_master.xlsx` and is loaded by
`etl/load_nu_master.py` into the `nu_master_org_data` table. It carries
`Name`/`Region`/`City`/`CEEB` (the columns `crosswalk_matcher.py` expects by
default) plus a wide set of org-level detail — SAT/AP participation and
scores, financial aid %, college-going rates, demographics, lat/long, etc.
Three constant section-divider columns from the source export
(`----`, `--Org Details--`, `--Org Details--School Profile Info--`) are
dropped on load; they carry no data. 2 of the 44,899 rows have no CEEB
("Explore Colleges", "Model United Nations" — non-school entries, not real
orgs) and are excluded from CEEB-keyed joins.

## Tables this produces

- `nu_master_org_data` — raw load, one row per org (PK: `guid`).
- `ib_ceeb_crosswalk`, `isbe_ceeb_crosswalk`, `cps_ceeb_crosswalk` —
  built by `etl/build_ceeb_crosswalk.py`'s `build_all()`, fuzzy-matching
  each source (which carries no CEEB of its own) against this master list.
  Each row has a confidence tier (`auto_accept` / `review` / `reject` /
  `no_candidate`) — **`ib_ceeb_crosswalk` has 0 auto-accepts by design**
  (see the code comment in `combine_schools.py`: IB has no state/city field
  to block on, so common institutional names collide nationwide — every IB
  match is capped at `review` regardless of score).
- `schools_org_enriched` (`etl/combine_schools.py`) — a separate, more
  direct combination: `schools_combined_enriched_ceeb` (a nationwide
  public+private school export already carrying an exact-match CEEB column
  via the UC Boulder crosswalk, see `data/CEEB-Crosswalk/README.md`)
  left-joined straight to `nu_master_org_data` on CEEB. No fuzzy matching
  needed here since both sides already have CEEB. 18,580 of 25,577 schools
  (73%) matched.

## If a newer file arrives

Overwrite `data/NU-Master/nu_master.xlsx` (or point `NU_MASTER_PATH`
elsewhere) and re-run `etl/run_all.py` — every step above re-derives from
whatever's at that path.
