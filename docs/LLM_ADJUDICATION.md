# LLM adjudication of CEEB review-tier matches — 2026-07 run

Problem: the NCES↔CEEB junction left 5,416 public + 290 private candidate pairs in
`tier=review` — too many for hand review, too error-prone for blanket thresholds. This run
resolves **all of them** with a three-stage funnel. Outputs:
`csv_exports/nces_{public,private}_ceeb_crosswalk_adjudicated.csv` (every row gets
`final_tier`, `decision_source`, `CEEB_final`; original auto_accept/reject rows pass through).

## Funnel

| Stage | Public | Private |
|---|---|---|
| review rows in | 5,416 | 290 |
| Rule: same city + name-superset (set≥95) → accept | 1,759 | 28 |
| Rule: same city + symmetric distinctive tokens → accept | 450 | — |
| Rule: diff city + weak ordered name (sort<72) → reject | 847 | 70 |
| Rule: diff city + no city-containment → reject | 1,904 | — |
| Rule: city-containment + set≥90 + tokens → accept | 13 | — |
| **LLM (Claude, in-session) judged** | **443** | **192** |
| … of which accept | 232 | 12 |
| … review kept (ambiguous) | 0 | 1 |

Final tiers — public: 14,096 accept / 10,087 reject; private: 550 accept / 803 reject / 1 review.
Versus the pre-adjudication state, **+2,460 public and +40 private schools** gained a usable CEEB
(review rows previously counted as unusable).

## Rule design rationale

- Same-city pairs are mostly abbreviation variants ("Pioneer Jr-Sr" ↔ "Pioneer Junior-Senior"),
  but ~25% are traps: an *alternative / virtual / continuation / jail / boot-camp / tech-center*
  program fuzzy-matching its district's regular high school. The symmetric-distinctive-token rule
  (strip generic words, require both name's distinctive tokens to cover each other with prefix
  tolerance) passes the former and routes the latter to the LLM.
- Different-city pairs are ~90% wrong (the true school has no CEEB, so the matcher grabbed a
  same-name school elsewhere). Since a wrong CEEB is worse than a missing one, these reject
  unless one city name contains the other (e.g. "QUINCY" ⊂ "NORTH QUINCY").

## LLM stage

Claude judged the 635 residual pairs with school-name domain knowledge (renamings like
"Flint Southwestern Academy" ↔ "Southwestern Classical Academy"; campus-split cases like the
Lincoln West schools sharing a legacy building/CEEB; distinguishing NYC's many near-name
schools like "Bronx Haven" vs "Bronx Theatre"). Verdicts are conservative: multi-state name
collisions without corroborating detail were rejected. Provenance is recorded as
`decision_source = llm_claude_fable_5` — filterable if a stricter standard is wanted later.

## Reuse

`etl/llm_adjudicate_matches.py` reruns the same funnel against the Anthropic API for future
crosswalk refreshes (needs `ANTHROPIC_API_KEY`; rules resolve ~88% before any tokens are spent).
The same pattern applies to the IB and ISBE/CPS name matches.

## Known limitations

- LLM verdicts rest on background knowledge of school renamings/campuses, which can be stale;
  the audit trail keeps every original score so any decision can be revisited.
- Public rows judged by the diff-city reject rule include some true matches in renamed or
  adjacent-town situations (accepted loss, quantified by the city-subset exception).
- 9th-grade centers and separate alternative campuses were rejected by design even when they
  feed the matched school — CEEB codes should attach to the institution that reports to
  College Board.
