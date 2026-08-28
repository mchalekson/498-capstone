# Deliverables — review index for Bob & Adam

Everything below is already in this repo. This page is the map: what each artifact is,
which version is current, and what we'd most like you to push on.

**Reading budget.** If you have 20 minutes, read the three "Start here" items. If you have
an hour, add Section 3. Everything else is reference you can pull on demand.

**Current data freeze:** `modeling_dataset_v4_2026-08-01.csv` — 34,392 US high schools
(public + private, grades 9–12 enrollment ≥ 30), keyed on `ceeb`, rebuilt on 2026-08-01 from
your extended org export. Pinned in code as `FREEZE_TAG = "v4_2026-08-01"`
(`etl/load_modeling_layer.py`). Every number in every document below traces to this freeze
unless the document says otherwise.

---

## Start here

| # | Artifact | What it is |
|---|---|---|
| 1 | [`docs/Bob_Week6_Update.pptx`](docs/Bob_Week6_Update.pptx) | The Week-6 client update, 11 slides — structured as "in Week 5 you asked for five things; here is each one built." Talk track in [`docs/PRESENTATION_SCRIPT.md`](docs/PRESENTATION_SCRIPT.md). |
| 2 | [`docs/RIGOR_CLASSIFICATION.md`](docs/RIGOR_CLASSIFICATION.md) | The rigor index itself — the core methodological deliverable. A transparent weighted composite cut into five ordinal tiers, *not* a supervised classifier (no ground-truth labels exist for this problem). Read this before anything else in Section 3. |
| 3 | [`docs/COVERAGE_BIAS.md`](docs/COVERAGE_BIAS.md) | Who has data and what the index does to schools that don't. The second half is an open finding we consider blocking for model sign-off — this is the document most likely to generate the questions worth spending Friday on. |

---

## 1. Written report

| Artifact | Status |
|---|---|
| [`written-report-iterations/MSDS_498_EDA_Report_tex.pdf`](written-report-iterations/MSDS_498_EDA_Report_tex.pdf) | Current EDA report (LaTeX build). Source: `MSDS_498_EDA_Report.tex`. |
| [`written-report-iterations/MSDS_498_Test_Plan_tex.pdf`](written-report-iterations/MSDS_498_Test_Plan_tex.pdf) | Current test plan (LaTeX build). Source: `MSDS_498_Test_Plan.tex`; full detail in [`docs/TEST_PLAN.md`](docs/TEST_PLAN.md). |
| `methods_rigor_tiering.tex`, `methods_clustering.tex`, `methods_predictive_validation.tex` | Methods sections drafted for the final paper, not yet merged into the main document. |

Superseded, ignore: `MSDS_498_EDA_Report.pdf`, `MSDS_498_Test_Plan.pdf`/`.docx`,
`MSDS_498_version-wk3.pdf`.

## 2. Presentations

| Artifact | Status |
|---|---|
| [`docs/Bob_Week6_Update.pptx`](docs/Bob_Week6_Update.pptx) | **Current** client deck. |
| [`docs/MSDS_498_Midterm.pptx`](docs/MSDS_498_Midterm.pptx) | **Current** midterm deck, 16 slides. Note the naming trap: this file is newer than `MSDS_498_Midterm_v2.pptx` despite the "v2" — the v2 file is the older July build and is superseded. |
| [`docs/PRESENTATION_SCRIPT.md`](docs/PRESENTATION_SCRIPT.md) | Talk tracks for both Week-6 decks, with cut lists for shorter slots. |
| `docs/Bob_Week5_CheckIn.pptx` / `.pdf` | Prior client check-in, kept for continuity — the Week-6 deck answers it point by point. |

## 3. Methodology — the analytical core

| Document | What it covers | Where it stands |
|---|---|---|
| [`docs/RIGOR_CLASSIFICATION.md`](docs/RIGOR_CLASSIFICATION.md) | v4 index: six components, weights, tier cutpoints, sensitivity | **Shipped** — this is what the freeze, dashboard, clustering and benchmarking all sit on |
| [`docs/RIGOR_FORMULA_V5.md`](docs/RIGOR_FORMULA_V5.md) | A formal v5 respecification on the wider 45,250-school universe | **Parallel build, not adopted** — fully specified with its own audit trail, but nothing downstream consumes it. v4 and v5 disagree substantially. See the open question below. |
| [`docs/RIGOR_SCENARIOS.md`](docs/RIGOR_SCENARIOS.md) | The two v4 revisions (AP qualifying density, IB intensity v2) | Adopted 2026-07-26, now the shipped default |
| [`docs/RIGOR_ANALYSIS.md`](docs/RIGOR_ANALYSIS.md) | AP efficiency + validation lenses built from Week-5 client ideas | Complete; neither changes the composite |
| [`docs/COVERAGE_BIAS.md`](docs/COVERAGE_BIAS.md) | What missing data does to a school's tier | **Open finding** — see below |
| [`docs/PREDICTIVE_VALIDATION.md`](docs/PREDICTIVE_VALIDATION.md) | Does the rigor construct predict outcomes it should? Train/test split | Complete |
| [`docs/CLUSTERING.md`](docs/CLUSTERING.md) | PCA + k-means peer grouping. Deliberately excludes `rigor_score` as an input | Complete; k = 8 |
| [`docs/BENCHMARKING.md`](docs/BENCHMARKING.md) | A school's SAT percentile within its peer group | Complete, descriptive only by design |

## 4. Data and dictionaries

The full export set is in [`csv_exports/`](csv_exports/) (135 files, including every prior
version — match the `v4_2026-08-01` tag to stay on the freeze).

| Artifact | What it is |
|---|---|
| `csv_exports/modeling_dataset_v4_2026-08-01.csv` | The freeze: 34,392 schools × 57 variables |
| `csv_exports/data_dictionary_modeling_dataset.csv` | Its dictionary — one row per variable with source, grain, vintage, confidence, range, % non-null |
| [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md) + `docs/data_dictionary_schools_org_enriched.csv` | Dictionary for the *raw joined* table, 127 variables — a different, wider table than the freeze |
| [`docs/DATA_DICTIONARIES_2026-08-02.xlsx`](docs/DATA_DICTIONARIES_2026-08-02.xlsx) | Both dictionaries in one workbook, if that's easier to read |
| `csv_exports/rigor_classification_v4_2026-08-01.csv` | Per-school score + tier |
| `csv_exports/clustering_v4_2026-08-01.csv`, `cluster_profiles_v4_2026-08-01.csv` | Peer groups and their interpretable profiles |
| `csv_exports/benchmarking_v4_2026-08-01.csv` | Peer-relative test-score percentiles |

## 5. Dashboard

[`dashboard/`](dashboard/) — a Streamlit app over the freeze. It imports the pipeline's own
scoring functions rather than reimplementing them, so the rigor explorer reproduces the
pipeline exactly. Pages: overview, live rigor-weight explorer (v4), v5 index, clustering,
benchmarking, crosswalk status, school lookup.

```bash
pip install -r dashboard/requirements.txt && cd dashboard && streamlit run app.py
```

The rigor explorer is the most useful thing here for a reviewer: move the six component
weights and watch tiers recompute, with Spearman against the shipped scheme and the % of
schools that change tier. It never writes a file — it's a what-if tool.

## 6. Linkage and coverage

| Document | What it establishes |
|---|---|
| [`docs/COVERAGE_REPORT.md`](docs/COVERAGE_REPORT.md) / [`.pdf`](docs/COVERAGE_REPORT.pdf) | Federal school roster vs. the NU master list — headline coverage and the gap list |
| [`docs/OPE_CEEB_MERGE_REPORT.md`](docs/OPE_CEEB_MERGE_REPORT.md) / [`.pdf`](docs/OPE_CEEB_MERGE_REPORT.pdf) | College-side OPEID ↔ CEEB junction plus College Scorecard enrichment |
| [`docs/COLLEGE_CLUSTERING_REPORT.pdf`](docs/COLLEGE_CLUSTERING_REPORT.pdf) | College clustering built on that junction |
| [`docs/LLM_ADJUDICATION.md`](docs/LLM_ADJUDICATION.md) | How 5,416 public + 290 private ambiguous CEEB pairs were resolved — three-stage funnel, every row gets a reason |
| [`docs/MATCH_RATE_RECONCILIATION.md`](docs/MATCH_RATE_RECONCILIATION.md) | Why different documents quote different match rates, and which one to cite (64.5%) |
| [`docs/COVERAGE_BY_SECTOR.md`](docs/COVERAGE_BY_SECTOR.md), [`docs/IB_RESCUE.md`](docs/IB_RESCUE.md) | Sector-level coverage; recovery of IB-school matches |

## 7. Responses to you

| Document | What it is |
|---|---|
| [`docs/MEETING_NOTES_2026-08-03_RESPONSES.md`](docs/MEETING_NOTES_2026-08-03_RESPONSES.md) | Point-by-point responses to the week-of-8/3 notes — field list, generic CEEBs, correctional facilities, HS clusters |
| [`docs/BOB_BRIEFING.md`](docs/BOB_BRIEFING.md) | Database overview written for you: what's in it, how it's built, open data gaps |
| [`docs/TEAM_BRIEF.md`](docs/TEAM_BRIEF.md) | One-page summary of where the rigor model stood at Week 5 |

---

## What we'd most like you to push on Friday

These are live disagreements or open decisions, not polish items. Questions here are worth
more to us than questions about anything above.

1. **v4 or v5?** Two complete rigor indices exist on two different school universes (34,392
   vs 45,250) and they disagree substantially. Everything downstream currently sits on v4.
   The paper has to pick one and defend the choice. See `docs/RIGOR_CLASSIFICATION.md` and
   `docs/RIGOR_FORMULA_V5.md`.
2. **Coverage bias.** A school with missing data does not score neutrally — it scores
   *differently*, in a direction that correlates with who gets visited. `docs/COVERAGE_BIAS.md`
   documents this and we do not consider it resolved.
3. **Is the composite the right shape at all?** The index is a transparent weighted composite,
   chosen because no ground-truth rigor labels exist to train against. If you think there's a
   labelling source we haven't considered, that changes the project.
4. **Clustering excludes rigor by design** (`docs/CLUSTERING.md`) so that peer groups and rigor
   stay independent constructs. Worth confirming that matches how you'd use peer groups.
5. **Benchmarking is descriptive only** — it ranks, it doesn't attribute causation. If you need
   it to support "school X is outperforming," that's a different piece of work.

## What isn't in this index

- **Raw source data** (~2.6 GB: CRDC, EDFacts, the org exports) is gitignored — it's past
  GitHub's limits. It lives in the team Drive folder linked from [`README.md`](README.md).
- **The live Postgres database** is a stale 2026-07-05 snapshot containing pipeline stages 1–2
  only. Don't cite it. `csv_exports/` is the authoritative current state, as `README.md` says.
