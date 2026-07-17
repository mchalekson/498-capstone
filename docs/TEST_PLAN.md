# Test Plan

Covers unit, integration, system, and user acceptance testing for the NU high-school data
platform (Sections 3-4 of `written-report-iterations/MSDS_498_version-wk3.pdf`). This is not
a generic template — every scenario below is grounded in a specific, real risk already found
in this pipeline (several of them actual bugs fixed during development; see the "why this
test exists" notes throughout). A runnable test suite backing this plan lives in `tests/`
(55 automated tests, all passing as of this writing — see Test Execution Plan for how to run
them).

---

## 1. Test Coverage

Four testing types, matched to where risk actually concentrates in this project:

| Type | What it covers | Why it matters here |
|---|---|---|
| **Unit** | Individual functions in `etl/build_features.py`, `etl/combine_schools.py` (its two pure-Python helpers only — see gap below), `etl/build_rigor_classification.py`, `etl/build_modeling_dataset.py` | This is where the real bugs have lived: sector misclassification, IB match-tier gating, LEAID derivation, the CEEB fan-out — all were logic errors inside single functions, catchable in isolation |
| **Integration** | How the CSV-driven pipeline stages compose (`build_features.build()` → `build_modeling_dataset`'s freeze steps) | Catches column-contract breaks between stages that unit tests on either side, run alone, can't see |
| **System** | The five-script CSV pipeline run end to end against the real exported data (`csv_exports/`) | Confirms the whole CSV-driven chain actually runs, not just that each piece is individually correct; this is also where the missing `scikit-learn` dependency (see §4) was caught |
| **User Acceptance (UAT)** | Planned reviews of the two data dictionaries, `modeling_dataset.csv`, and the rigor/clustering/benchmarking outputs, by the project client (Bob Henkins, NU Undergraduate Admissions, and Adam) and, per the assignment's "we may engage the other team," a second student team | The platform's entire purpose (per the report's Section 1) is serving admissions officers standardized, auditable context — correctness by our own tests is necessary but not sufficient; the client has to find the output usable |

**Two coverage gaps, stated plainly rather than glossed over:**

1. **`etl/combine_schools.py`'s actual join logic is untested.** Only its two pure-Python
   helpers (`resolve_ceeb_ties`, `normalize_name`) have unit tests. The functions that do the
   real work — `build_schools_org_enriched`, `build_schools_org_all`,
   `build_public_schools_enriched`, `build_private_schools_enriched`,
   `build_cps_nces_crosswalk` — run SQL against a live Postgres database and have **zero**
   automated coverage, and no documented manual verification procedure either. This is the
   riskiest code in the pipeline (multi-table joins, state-context merges, IB/ISBE/CPS fuzzy
   matching) and it's currently the least tested. See §4 for why, and §5/§6 for the plan to
   close this.
2. **The Docker/Postgres system test is not currently automatable or reproducible from a
   fresh clone**, for a deliberate, correct reason (not an oversight — see §4): the raw source
   files that database-backed step needs (`data/updated-sheng/`) total roughly 2.6 GB
   (a single CRDC data folder alone is 794 MB, two EDFacts assessment folders are 1.7 GB and
   1.8 GB) and were intentionally excluded from git as impractical to version, not just
   over GitHub's per-file limit. A fresh `git clone` of this repo has no way to obtain them,
   so `docker compose up` + `etl/run_all.py` cannot currently be exercised as an automated
   test. Documented as a real, standing limitation in §4, not worked around silently.

Explicitly **not** covered by this plan (documented, not silently skipped):
- Load/performance testing — out of scope; this is a batch ETL pipeline re-run at most annually
  (per the report's reproducibility goal), not a service under concurrent load.
- Security testing — the platform has no external-facing API or auth surface yet; revisit if
  one is added.

---

## 2. Test Scenarios

### Unit test scenarios (by module)

**`build_features.py`**
- Bucket-midpoint parsing across every observed format: exact ranges (`"26% - 50%"`),
  open-ended high (`"Over 90%"`, `"greater than 20"`), open-ended low (`"10% or fewer"`),
  bare numbers (`"0"`), unparseable strings, and null input.
- Winsorization clips extreme outliers at the 1st/99th percentile without crashing on
  all-null input.
- Sector classification: public HS, private HS via `nu_type`, private HS via a school-side
  `pss_id` record with **no** `nu_type` (the exact case a real bug missed), an org-only row
  with no school-side match, and mutual exclusivity of public/private flags.
- IB flag gating: `review`-tier match counts as a candidate, `reject`-tier does not (a real
  bug counted both), no-match rows are `0` not null.
- LEAID derivation: correctly takes `nces_id_12[:7]`, returns null when `nces_id_12` is
  itself null (never falls back to the broken 5-character `leaid` column).

**`combine_schools.py`**
- Name normalization: `"Saint"` → `"ST"`, `"HS"` → `"HIGH SCHOOL"`, punctuation stripping,
  null-safe.
- CEEB tie resolution: best-tier match keeps the CEEB, the loser gets nulled and flagged;
  ties at equal tier prefer an exact name match; a frame with no duplicates is untouched;
  a unique CEEB is never modified.

**`build_rigor_classification.py`**
- Z-scoring: mean-zero/std-one on normal input, all-NaN on zero-variance input (must not
  divide by zero), NaN passthrough.
- Weighted composite: matches a plain weighted average under full coverage; **reallocates
  weight proportionally** when a component is missing (not zero-imputed, not row-dropped);
  yields NaN (not 0) when zero components are available; a zero-weight component (IB in the
  default scheme) never influences the score even when present.
- Tier assignment: five roughly-equal quintile buckets, correct ordinal ordering (lowest
  score → "Below Average"), NaN scores stay untiered rather than defaulting to a tier.

**`build_modeling_dataset.py`**
- Minimum-size freeze: drops schools below the enrollment floor, **keeps** schools with
  unknown (null) enrollment rather than treating null as "too small," boundary value is
  inclusive.
- Universe restriction: only public/private HS rows survive; `other/oos` is dropped.
- Sentinel scrub: negative sentinel codes in rate/score-named columns become null; a
  legitimate `0` is untouched; a non-suspect column name is never scrubbed even if it
  contains a value that would be a sentinel elsewhere.

### Integration test scenarios
- The synthetic fixture (covering public HS, private-via-`pss_id`, private-via-`nu_type`,
  and org-only rows) survives `build_features.build()` → universe restriction → min-size
  freeze with sector labels intact and no row collapsing into another.
- No duplicate school identities emerge from chaining these steps (a stand-in for the class
  of bug the real CEEB fan-out was).

### System test scenarios (automated, verified)
- Each of the five pipeline scripts (`build_features.py`, `build_modeling_dataset.py`,
  `build_rigor_classification.py`, `build_clustering.py`, `build_benchmarking.py`) runs to
  completion against the real `csv_exports/` data and produces output of the expected shape
  (row-count floor, required columns present, categorical outputs constrained to their valid
  value sets). Verified: all 5 pass as of this writing.

### System test scenario NOT currently achievable — a real, standing gap
- `docker compose up` bringing up Postgres 16 and the ETL container, followed by
  `etl/run_all.py` completing against a freshly created database, **cannot currently be run
  as an automated test.** It was never executed as part of building this suite. On a fresh
  clone it would fail at the loader step: `etl/load_schools_ceeb.py` and
  `etl/combine_schools.py` need files under `data/updated-sheng/` that are gitignored and
  were never committed (correctly — see §4 for the actual sizes involved). Closing this gap
  needs a decision, not a workaround: either commit a small sanitized fixture version of
  those files for testing purposes, or document exactly where the real files live and how a
  new contributor obtains them, and accept that this system test stays manual until then.

### UAT scenarios (planned — none of these have happened yet)
- Bob/Adam can locate, in `data_dictionary_schools_org_enriched.csv` and
  `data_dictionary_modeling_dataset.csv`, the source, vintage, and description for any
  variable they ask about — this is literally what they asked for in the 2026-07-14 meeting.
- A reviewer unfamiliar with the pipeline can open `modeling_dataset_v1_2026-07-17.csv` and
  correctly interpret `rigor_tier_label`, `sector`, and `funding_source` from the data
  dictionary alone, without needing to read the ETL code.
- The "other team" (per the assignment's UAT engagement note) can independently reproduce
  one full pipeline run from `csv_exports/` and get matching row counts, without any of our
  team walking them through it live.

---

## 3. Test Case Design

Full test cases live as executable code in `tests/` (not just described here, so they can't
drift out of sync with the actual pipeline). Representative examples, in the format the
rubric asks for (steps / data input / expected result):

| ID | Test | Input | Steps | Expected result |
|---|---|---|---|---|
| UT-01 | `test_is_private_hs_via_pss_id_only` | Fixture row: `school_id="S2"`, `pss_id="P1"`, `nu_type=NaN`, `school_level=NaN` | Run `build(df)` | `is_private_hs == True`, `sector == "private"` — regression test for a real bug where such rows fell into `"other/oos"` |
| UT-02 | `test_reject_tier_does_not_count` | Fixture row with `ib_school_id` set, `ib_match_tier="reject"` | Run `build(df)` | `ib_flag_candidate == 0` — regression test for a real bug where reject-tier matches were counted as confirmed |
| UT-03 | `test_missing_component_reallocates_weight_proportionally` | `comp = {"a":[1, NaN], "b":[3,4], "c":[5,6]}`, `weights={"a":.5,"b":.25,"c":.25}` | Call `weighted_composite(comp, weights)` | Row 1 score = `4*.5 + 6*.5` (weight renormalized over available components) |
| UT-04 | `test_keeps_the_best_tier_match` | Two schools sharing CEEB `050222`: one `auto_accept` exact-name match, one `review`-tier different school | Call `resolve_ceeb_ties(df)` | `auto_accept` row keeps the CEEB; `review` row's CEEB is nulled and flagged |
| IT-01 | `test_full_chain_on_fixture` | 4-row fixture (public HS, 2 private HS variants, 1 org-only) | `build()` → `restrict_to_hs_universe()` → `apply_min_size_freeze()` | Only public/private rows remain; each is public XOR private; the pss_id-only private school survived the chain |
| ST-01 | `test_build_rigor_classification` (system) | Real `modeling_dataset_v1_*.csv` (34,392 rows) | Run `build_rigor_classification.py` via subprocess | Exit code 0; output has `rigor_tier_label`; every non-null value is one of the five valid tier names |

Adding a test case: any new bug found gets a regression test named for the bug, not just the
function — matches the pattern already used throughout (see `test_build_features.py`'s
docstring, which explains this convention directly).

---

## 4. Test Environment Setup

**Two supported environments**, matching how this pipeline is actually run day to day:

1. **CSV-only (no database)** — what most contributors use. Requires Python 3.11+ (matches
   `etl/Dockerfile`'s `python:3.11-slim`; developed/tested here on 3.13.5) and the packages
   pinned in `etl/requirements.txt`. Operates directly on `csv_exports/*.csv`; this is what
   the system tests (§1) run against.
2. **Full Docker stack** — `docker-compose.yml` brings up Postgres 16 (`capstone-db`,
   port 5433→5432) and an ETL container (`capstone-etl`, built from `etl/Dockerfile`) that
   runs `etl/run_all.py` against it. Needed for `combine_schools.py`'s SQL-backed builds and
   anyone re-deriving `csv_exports/` from raw source data rather than reading the already-
   exported CSVs.

   **Not currently reproducible from a fresh clone, on purpose, not by accident.**
   `data/updated-sheng/` — Sheng's combined schools export, Bob's org export, and the raw
   CRDC/EDFacts assessment data — is gitignored. This was a deliberate call, not an
   oversight: the directory is roughly **2.6 GB** (CRDC data alone is 794 MB; two EDFacts
   assessment folders are 1.7 GB and 1.8 GB), far past what's reasonable to version in git
   regardless of GitHub's 100 MB per-file limit. The real consequence: anyone testing the
   Docker/Postgres path needs these files placed manually, from wherever the team currently
   shares them, before `etl/run_all.py` can run at all — and that hand-off isn't documented
   anywhere yet. Recommendation: either (a) generate and commit a small, sanitized fixture
   version of each file, scoped to just enough rows to exercise the joins, purely for testing
   — or (b) write down, in this repo, exactly where the real files live and how to get them.
   Until one of those happens, the Docker/Postgres path is tested manually and
   inconsistently, not automatically.

**Test-specific dependencies**: `requirements-test.txt` (pytest 9.1.1) — kept separate from
`etl/requirements.txt` since pytest is a development/test-time dependency, not a pipeline
runtime one.

**A real environment gap this test plan already caught**: `etl/requirements.txt` was missing
`scikit-learn`, which `build_clustering.py` requires — meaning the documented Docker
environment could not actually run that script. Fixed as part of writing this plan (see
`etl/requirements.txt`), not a hypothetical example.

**Configuration**: `etl/config.py` reads `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASS`
from environment variables (defaults: `localhost:5432/capstone/postgres`), overridden by
`docker-compose.yml`'s `capstone`/`capstone`/`capstone` when run in Docker. `NU_MASTER_PATH`
and `SCHOOLS_CEEB_PATH` point at the raw data files under `data/`.

**Running the suite**:
```
pip install -r requirements-test.txt -r etl/requirements.txt
pytest tests/ -v
```
System tests (`test_system_pipeline.py`) auto-skip if `csv_exports/schools_org_all.csv`
isn't present, so the suite still runs (unit + integration only) on a checkout without the
data exports.

---

## 5. Test Execution Plan

Tied to the project's own weekly schedule rather than an invented cadence. **Ownership below
is honest about what is and isn't formally assigned**: no RACI document exists in this repo —
`docs/BOB_BRIEFING.md` references "per the RACI, master database & data pulls is Max/Qifan's
workstream," which is the closest documented scope to this pipeline's code, but no RACI
covering *testing* specifically has been written. Where a name is used below, it's inferred
from that one existing reference, not from a formal assignment — flagged as its own action
item, not silently assumed.

| Phase | When | What runs | Who |
|---|---|---|---|
| Unit + integration, every commit | Ongoing, starting now (Week 4) | `pytest tests/test_build_features.py tests/test_combine_schools.py tests/test_build_rigor_classification.py tests/test_build_modeling_dataset.py tests/test_integration_pipeline.py` | Whoever touches `etl/*.py` — run locally before pushing; no CI is wired up yet (see Defect Management), so this is currently a manual discipline, not an enforced gate |
| System test, before every new versioned dataset | Whenever `modeling_dataset_v<N>` is cut | `pytest tests/test_system_pipeline.py` | Whoever cuts the version |
| Full Docker system test | Not currently runnable (see §4) — this row describes the target state, not a running practice | `docker compose up`, then `etl/run_all.py` end to end | Closest existing RACI scope: Max/Qifan ("master database & data pulls" per `BOB_BRIEFING.md`) — needs explicit confirmation, not assumed |
| Hyperparameter/validation-specific testing | Week 7 (per the project's own schedule — Section 4.6 of the report) | Train/test/validation split checks, overfitting/underfitting checks — not yet built, this plan's system/integration tests are the pre-requisite groundwork for that phase | Not assigned — no RACI line covers modeling/validation specifically; needs a decision, not a default |
| UAT round 1 | As soon as Bob/Adam have bandwidth (not gated on a specific week) | Structured review of both data dictionaries + `modeling_dataset.csv`, using the UAT scenarios in §2 | Bob, Adam |
| UAT round 2 (peer team) | Before Week 9 presentation prep | The engaged "other team" independently reproduces one pipeline run and reviews the rigor/clustering/benchmarking docs for clarity | Second student team + our team |

**Dependencies**: system tests depend on `csv_exports/` being current (regenerate via the
chain in §1 before running); UAT round 2 depends on round 1 feedback being incorporated
first, so the peer team isn't reviewing something already known to be wrong. The Docker
system test row depends on §4's fixture-or-documentation decision being made first — it
cannot run at all until then.

**Action item surfaced by writing this plan**: a real RACI covering test ownership
specifically doesn't exist yet. Recommend the team produce one (even a short one) rather than
this plan inferring ownership from a single line in `BOB_BRIEFING.md`.

---

## 6. Defect Management

No formal issue tracker is wired up yet — this section states the process going forward,
not one already running.

- **Reporting**: defects found via testing (automated or manual/UAT) get filed as GitHub
  Issues on `mchalekson/498-capstone`, tagged by the pipeline stage affected (`etl`,
  `rigor-classification`, `clustering`, `benchmarking`, `data-quality`). Each issue states:
  what broke, the failing test (if automated) or the specific input that triggered it, and
  expected vs. actual output — the same information already present in this session's
  fix commits (e.g., the CEEB fan-out fix commit documents the exact failing pattern with
  real school names and CEEB values).
- **Severity tiers**:
  - **Blocking**: breaks a pipeline stage outright (e.g., the missing `scikit-learn`
    dependency) — fix before the next system test run.
  - **Data-quality**: produces output but the output is wrong (e.g., the CEEB fan-out, the
    IB sector-classification bug) — fix before the next versioned `modeling_dataset` cut,
    documented in the relevant `docs/*.md` memo regardless of fix timing.
  - **Documentation**: code and docs disagree but the code itself is fine (e.g., the
    `parse_bucket_midpoint` docstring typo found while writing this plan's tests) — low
    priority, batched into the next doc-touching commit.
- **Tracking**: issue status (open/in-progress/resolved) lives on the GitHub Issue itself;
  no separate spreadsheet, to avoid the two-sources-of-truth problem this project has
  already flagged for data vintage tracking.
- **Resolution verification**: every defect fix ships with a regression test named for the
  bug (see §3's convention) — a defect isn't "resolved," it's resolved-and-covered.

---

## 7. Regression Testing

- **When**: the full unit + integration suite (`pytest tests/ -k "not system"`) runs before
  every commit that touches `etl/*.py`, not on a fixed calendar cadence — appropriate for a
  small team iterating quickly rather than a large one needing a scheduled batch window.
- **What**: every previously-found bug in this pipeline has a corresponding test (the
  sector-classification bug, the IB gating bug, the LEAID derivation bug, the CEEB fan-out,
  the docstring/behavior mismatch in `parse_bucket_midpoint`) — regression here specifically
  means "did a fixed bug come back," not just "did anything change."
- **Full-pipeline regression**: the system test suite reruns the entire five-script chain
  against the current `csv_exports/` data whenever any script in that chain changes, catching
  regressions that only manifest at real production scale (small-fixture unit tests can miss
  scale-dependent issues, like the quintile-tier bucketing needing a large-enough population).
- **No CI yet**: this is a real gap, not glossed over — recommend wiring up GitHub Actions to
  run the non-system tests on every push once the team has bandwidth, so regression testing
  stops depending on individual discipline.

---

## 8. Documentation and Reporting

- **Format**: test results are reported the same way every other finding in this project has
  been — as dated updates in the relevant `docs/*.md` file (`EDA_features_joined.md`,
  `RIGOR_CLASSIFICATION.md`, `CLUSTERING.md`, `BENCHMARKING.md`), not a separate test-report
  artifact disconnected from the data findings they relate to. This test plan itself
  (`docs/TEST_PLAN.md`) is the canonical reference for test *process*; individual *results*
  stay attached to the deliverable they validate.
- **Frequency**: after every system-test run that precedes a new versioned dataset, and
  immediately whenever a defect is found (not batched) — per Defect Management's severity
  tiers, blocking and data-quality defects get documented in the relevant memo right away.
- **Recipients**: `docs/BOB_BRIEFING.md` is the client-facing summary channel — already the
  established pattern (it's flagged Bob-relevant items like the CEEB corruption finding
  throughout this project); test/defect findings that affect data Bob or Adam would review
  get added there specifically, not just to the internal EDA memos.
- **UAT reporting**: feedback from Bob/Adam and the peer team gets logged in
  `docs/BOB_BRIEFING.md`'s update sections (matching the existing "what we resolved
  ourselves" / "what we still need from you" structure already used there), so UAT feedback
  and technical defect tracking don't fragment into separate, hard-to-reconcile systems.
