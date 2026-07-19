# Match-rate reconciliation — why 64.5% and 47% are both "the match rate"

Two school↔NU-org match rates appear in this project's materials, and they look
like they contradict each other:

| Figure | Where it appears | Arithmetic |
|---|---|---|
| **64.5%** | `docs/BOB_BRIEFING.md`, `docs/DATA_DICTIONARY.md` | 16,508 / 25,577 |
| **47%** | derived from `modeling_dataset_v1`'s `is_school_match` | 16,111 / 34,392 |

**Neither is wrong, and they aren't measuring different matching.** The numerator
is the same population both times. Only the denominator changes — and the 47%
denominator includes ~12,560 rows that *cannot* match by construction, which
makes it the one figure of the three that should not be quoted on its own.

## The numerator is the same both times

`schools_org_enriched` has 16,508 rows with a populated `nu_guid` — that's the
64.5% numerator. That exact figure carries into the engineered frame:
`schools_features.csv` has `is_school_match == True` on 16,508 rows.

The freeze (HS universe + enrollment ≥ 30) then drops 397 of them, leaving
**16,111** in `modeling_dataset_v1`. So the entire numerator difference between
the two published figures is 397 schools lost to the freeze filters — not a
matching discrepancy.

## The denominators are different populations

`schools_org_enriched` (25,577 rows) is a **left join from the schools side**:
every row starts life as a school in Sheng's export. Every row is therefore
*eligible* to match.

`modeling_dataset_v1` (34,392 rows) descends from `schools_org_all`, a **full
outer join**, and then gets filtered to the HS universe. That outer join means
some rows are org records with no school-side counterpart at all. They survive
into the modeling dataset because they classify as private HS, but they have no
`school_id` — and `is_school_match` is defined as `school_id.notna() &
nu_guid.notna()`, so they are structurally incapable of ever being `True`.

Decomposing the 34,392:

```
total rows              34,392
  org-only (no school)  12,560   <- can never match, by construction
  school-side present   21,832
     matched to org     16,111
     unmatched           5,721
```

All 12,560 org-only rows are `sector == "private"` — an artifact of how private
schools enter this pipeline (many arrive only as NU org records, with no
school-side row to match against).

## The three defensible figures

| Rate | Denominator | What it answers |
|---|---|---|
| **64.5%** (16,508/25,577) | schools in Sheng's export | "Of schools we started with, how many did we match?" |
| **73.8%** (16,111/21,832) | modeling-dataset rows with a school-side record | "Within the frozen dataset, of rows that *could* match, how many did?" |
| **46.8%** (16,111/34,392) | all modeling-dataset rows | "What share of modeling rows carry a confirmed school↔org link?" |

**Recommended usage:**

- Quote **64.5%** for the joining/crosswalk work itself — it's the honest measure
  of how well CEEB matching performed, and it's what's already in Bob's briefing.
- Quote **73.8%** when talking about the modeling dataset's match quality. This is
  the apples-to-apples counterpart to 64.5% (it's higher because the freeze drops
  small and non-HS schools, which matched at below-average rates).
- Use **46.8%** only as a *coverage* statement, and always say what it's a share
  of: "47% of modeling rows carry a confirmed school↔org link." Never present it
  as the match rate — it silently penalizes the join for 12,560 rows the join was
  never offered.

## Practical implication for modeling

The relevant number for anyone selecting features is neither headline rate. It's
that **`is_school_match` is True for 16,111 of 34,392 rows**, and any feature
sourced from the NU org export is systematically missing outside that subset.
`has_nu_data` (28,671 rows) is the broader stratum — it only requires an org
record, not a confirmed school-side pairing — so the two flags stratify the
dataset differently and are not interchangeable.

---

*Reconciled 2026-07-19 against `csv_exports/modeling_dataset_v1_2026-07-17.csv`,
`schools_features.csv`, and `schools_org_enriched.csv`. The freeze population was
independently reproduced from `schools_features.csv` through
`build_modeling_dataset.py`'s own filter functions, landing at exactly 34,392
rows, which confirms the chain above.*
