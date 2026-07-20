# IB flag rescue — v2 methodology

Problem: the original IB input (`ib_flag_candidate`) came from fuzzy name-only matching of the
IBO scrape against school rosters. Zero matches cleared `auto_accept` (the IBO export has no
state/city), so RIGOR_CLASSIFICATION.md correctly excluded IB (weight 0) — while the sensitivity
run showed folding IB in would move 42% of schools across tiers. This doc describes the v2 flag
that removes the name-matching dependency for the public sector entirely.

## Method

**Public schools — authoritative, no matching.** CRDC 2021-22 collects IB enrollment directly
(`SCH_IBENR_IND`, `TOT_IBENR_M/F` in `SCH/International Baccalaureate.csv`), keyed by 12-digit
NCESSCH. Joined exactly via `nces_id_12`. Result: 19,884 public HS answered; **933 IB=yes**;
reserve codes (-3/-5/-9) treated as unanswered. Sanity: IBO's own DP/CP list has 934 US schools
(public + private) — same order of magnitude, consistent.

**Private schools — small-universe match + human adjudication.** IBO DP/CP schools (934) were
fuzzy-matched (token_sort ≥ 87) against the 1,354-school private roster only. All 73 candidates
were reviewed by hand against name/city/religious-affiliation and known IB school lists:
18 accept, 9 review (ambiguous multi-state name collisions — e.g. "Mercy High School",
"St. Andrew's School"), 46 reject. Full audit trail: `csv_exports/ib_rescue_private_matches.csv`.

## Output columns (in schools_combined_enriched_ceeb.csv)

- `crdc_ib_offered` (0/1), `crdc_ib_enrollment` — raw CRDC values, public only
- `ib_flag_v2` — 1/0 usable flag: public = CRDC; private = adjudicated accepts (unmatched private = 0)
- `ib_flag_v2_source` — `crdc_2122` or `ibo_name_match_adjudicated`

Coverage: 21,238 / 25,577 schools have a definitive 0/1 (public unanswered CRDC rows stay NaN).

## Hand-off to the rigor model

`ib_flag_v2` (and `crdc_ib_enrollment / enrollment_9_12` as an intensity measure) can now enter
the IB component of `build_rigor_classification.py` with real weight. Suggested: rerun the
`ib_included` sensitivity scenario using `ib_flag_v2` instead of `ib_flag_candidate` and compare
tier stability before adopting.

## Caveats

- CRDC vintage is SY 2021-22; schools authorized since then are missed (IBO scrape is 2025-26 —
  the 9 `review` rows and any new public authorizations could be cross-checked against IBO by
  state once locations are scraped).
- The 7 `review`-tier private pairs are excluded from `ib_flag_v2` (conservative). They are name
  collisions needing one fact-check each.
- Private universe is our grades-9–12-only roster; IB private schools outside it (e.g. K-12
  schools not in the PSS pull) are out of scope by design.
