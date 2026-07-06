# NCES ↔ CEEB crosswalk (third-party, external source)

`oda_nces_ceeb_crosswalk.csv` — 21,391 US secondary schools with both an
NCES ID and a CEEB code, pulled from the University of Colorado Boulder's
public crosswalk project:

- Source: https://github.com/UCBoulder/ceeb_nces_crosswalk
- License: **CC BY-SA 4.0** (attribution + share-alike — cite UC Boulder's
  Office of Data Analytics if this crosswalk is used in the final paper or
  redistributed)
- Last updated upstream: 2025-01-06 (incorporates a later contribution from
  Mark Davenport, UNC Greensboro)
- Built via three methods per the source repo: existing crosswalk sources,
  fuzzy name/zip matching, and Amazon Mechanical Turk manual verification —
  `match_source` (0/1/2) and `match_score` indicate which.

## Why this exists

College Board has no bulk public export of K-12 CEEB codes (verified —
only a one-at-a-time search tool). This is the closest thing to one:
independently built, but not an official NCES/College Board product, and
not the internal NU Admissions list Bob has. Treat it as a **supplementary,
best-effort source** — use it to seed a real NCES↔CEEB junction now, but
don't treat it as ground truth the way an official source would be.

## Known limitation in how we join it

`hs_nces` in this file is a standard 12-digit NCESSCH ID for ~19,365 of the
21,391 rows (the rest are 8-digit PSS private-school IDs). Our own
`nces_public_schools_clean.ncessch` is only the truncated 7-digit ELSI
export ID (see the ELSI re-pull item elsewhere in this repo), so a direct
ID join isn't possible yet — `etl/build_ceeb_crosswalk.py` matches by name
+ state instead. Once the ELSI export is re-pulled with the 12-digit ID,
this could upgrade to a direct ID join instead of fuzzy matching, which
would be meaningfully higher confidence.
