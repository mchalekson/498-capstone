# Design: An Annual-Refresh AI Agent for the School Master Database

Status: proposal (design only). Author: capstone team, July 2026.

## 1. Goal and non-goals

**Goal.** A single-command agent that, when new source vintages are released (CCD/PSS,
CRDC, EDFacts, ACS/SAIPE, IBO, NU org export), performs the full refresh cycle:
acquire data → validate → load → clean → rebuild the combined/modeling layers → re-run
the rigor classification and clustering → produce an evaluation report that explains
what changed and why.

**Non-goals.** This is not a general autonomous agent. The pipeline logic stays in
deterministic, tested Python (`etl/`); the agent orchestrates it. We do not let an LLM
transform data values, compute statistics, or assign tiers directly.

**Design principle: the agent orchestrates deterministic tools; it does not replace
them.** LLM judgment is reserved for the steps where the project has already proven it
pays off: entity matching adjudication, schema-drift handling, source discovery, and
report narration.

## 2. Architecture — four layers

```
┌────────────────────────────────────────────────────────────┐
│ 4. Governance: provenance tags, versioning, HITL gates,     │
│    golden-dataset regression tests                          │
├────────────────────────────────────────────────────────────┤
│ 3. Judgment (LLM): match adjudication · schema-drift        │
│    mapping · source discovery · report narration            │
├────────────────────────────────────────────────────────────┤
│ 2. Orchestration: explicit DAG / state machine;             │
│    agent intervenes only on failure or decision points      │
├────────────────────────────────────────────────────────────┤
│ 1. Tools: fetch_source · validate · load_* · clean_* ·      │
│    combine · build_models · compute_stats · export_report   │
└────────────────────────────────────────────────────────────┘
```

### 2.1 Tool layer

Wrap each existing pipeline stage as a callable tool with a typed contract
(inputs, outputs, side effects, idempotency) and structured logs. Most already exist:

| Tool | Backed by | Status |
|---|---|---|
| `load_*`, `clean_*`, `combine` | `etl/run_all.py` stages | exists |
| `build_modeling_dataset` | `etl/build_modeling_dataset.py` | exists |
| `build_rigor`, `build_clusters` | `etl/build_rigor_classification.py` etc. | exists |
| `adjudicate_matches` | `etl/llm_adjudicate_matches.py` | exists |
| `fetch_source(source_id, year)` | new: per-source config (URL template, expected schema, license notes) + Playwright fallback for JS-rendered portals (ED Data Express) | new |
| `validate(table, contract)` | new: row-count bounds, key uniqueness, null-rate ceilings, distribution drift vs. previous vintage (PSI/KS on key columns) | new |
| `compute_stats` → `stats.json` | new: every number the report will cite | new |
| `export_report(stats.json, template)` | new | new |

Requirements for every tool: idempotent re-runs, machine-readable result
(`ok | failed | needs_decision` + payload), no hidden state.

### 2.2 Orchestration layer

An explicit DAG (Claude Agent SDK, LangGraph, or a plain state-machine runner —
the framework matters less than the explicitness):

```
fetch → validate_raw → load → clean → validate_clean → combine
      → adjudicate (if new matches) → build_models → evaluate → report
```

The happy path runs with zero LLM calls. The agent is invoked only when a node
returns `failed` or `needs_decision`, with a bounded action space per node:

- **fetch 404 / layout change** → agent searches for the new release URL (agencies
  move files yearly — CRDC and ED Data Express both did in 2025-26), updates the
  source config, retries. Escalates if the source appears discontinued.
- **schema drift** → agent diffs new vs. expected columns, proposes a mapping
  (e.g. ELSI renaming `School ID (7-digit)` columns between pulls), writes it to the
  source config as a *proposal* requiring human approval before first use.
- **validation failure** → agent classifies: data defect (e.g. suppression-symbol
  change) vs. genuine world change (e.g. post-COVID graduation-rate rebound) vs.
  our bug. Fixes config-level issues; escalates the rest with a diagnosis attached.

Retry budget and cost ceiling per run; on exhaustion the run halts in a resumable state.

### 2.3 Judgment layer (where the LLM earns its keep)

Four tasks, all already prototyped in this project:

1. **Match adjudication** — the three-stage funnel from `docs/LLM_ADJUDICATION.md`:
   deterministic rules resolve ~88% of review-tier pairs; the LLM judges the residue;
   `unsure` stays for humans. Reused for CEEB, IB, ISBE/CPS matching whenever a roster
   refreshes.
2. **Schema-drift mapping** — propose column mappings on vintage changes (see 2.2).
3. **Source discovery** — locate moved/renamed release files; verify by checking the
   downloaded file's schema against the contract before accepting.
4. **Report narration** — the hard rule: **the LLM never computes or invents a
   number.** `compute_stats` produces `stats.json` (tier migration counts, coverage
   deltas, drift metrics, top movers with reasons); the LLM writes prose citing only
   those values, into a fixed template (summary → data changes → tier migrations →
   anomalies → limitations). A post-render check greps every numeral in the report
   against `stats.json` and fails the build on mismatch.

### 2.4 Governance layer

- **Provenance**: every AI-influenced value carries a source tag
  (`decision_source='llm_<model>'`, `imputed=true`, `extracted_from='school_profile_pdf'`),
  following the pattern already used in the adjudicated crosswalks and `ib_flag_v2_source`.
  Official data and AI-derived data are never mixed in one column without a flag.
- **Versioning**: datasets keep the `_vN_YYYY-MM-DD` convention; the DB gets a
  `vintage` table recording source → file hash → download date → schema version.
- **Human-in-the-loop gates** (hard stops, not advisories):
  1. tier-definition or weighting changes to the rigor model;
  2. first use of any schema mapping proposed by the agent;
  3. batch approval of `unsure` match adjudications.
- **Regression tests**: the existing `tests/` suite plus golden checks — a pinned set
  of ~30 known schools (New Trier in Most Demanding, etc.) whose tier/CEEB/IB values
  must survive a refresh unless the report explicitly justifies the change.

## 3. Run modes

| Mode | Trigger | Behavior |
|---|---|---|
| `refresh --source crdc --year 2023-24` | new single-source release | partial DAG from that source down |
| `refresh --all` | annual | full cycle, ends with diff report |
| `dry-run` | before any refresh | fetch + validate only; report what *would* change |
| `adjudicate` | after roster changes | funnel only |

## 4. Evaluation of the agent itself

- **Pipeline correctness**: golden regression suite (above) — hard fail.
- **Adjudication quality**: maintain a ~200-pair labeled holdout (we already have the
  hand-labeled 2026-07 decisions); measure precision on `accept` per run; alert if
  below 0.95. False-accept is the costly error (wrong CEEB), so tune thresholds
  toward reject.
- **Report faithfulness**: automated numeral-vs-`stats.json` check (2.3); spot-audit
  one section per run.
- **Ops metrics**: LLM tokens per run, human interventions per run, wall-clock. The
  target trend is interventions ↓ over vintages as source configs accumulate fixes.

## 5. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Silent schema drift corrupts a vintage | validation contracts + drift stats before load; proposals gated by HITL |
| Hallucinated numbers in reports | stats.json-only narration + numeral cross-check |
| Wrong CEEB attached by adjudicator | conservative funnel; reject-biased; provenance allows bulk revert |
| Source requires credentials/CAPTCHA | Playwright profile with stored session; else halt with a "manual download needed" task, resume after drop-in (the pattern used for CRDC/EDFacts this term) |
| Cost blow-up on retries | per-run token/cost ceiling; rules-before-LLM funnel design |
| Model version changes shift adjudication behavior | pin model versions in config; re-run labeled holdout on upgrade |

## 6. Implementation sketch (2–3 weeks of part-time work)

1. **Week A**: source config registry (`sources.yaml`: URL templates, schemas,
   licenses); `fetch_source` + `validate` tools; wire into a state-machine runner
   over the existing `run_all.py` stages.
2. **Week B**: `compute_stats` + report template + numeral check; diff report
   ("which schools changed tier and why") as the flagship output.
3. **Week C**: agent hooks for the four judgment tasks (adjudication already done);
   golden regression suite; dry-run mode; demo end-to-end on a simulated CRDC 2023-24
   drop.

The flagship demo: drop a new source file in, run `refresh`, and hand the committee a
report that says — with verified numbers — how the national school landscape moved.
