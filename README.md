# 498-capstone

ETL pipeline that loads NCES, Census, NAEP, ISBE, IB, CPS, and College Board
data into a Postgres database and combines it into school-level enriched
tables.

## Quickstart

Every table and view is already exported to CSV in [`csv_exports/`](csv_exports/) —
for most work (feature engineering, rigor classification, clustering, benchmarking)
you don't need Docker or Postgres at all, just the CSVs already in this repo.

To rebuild everything from raw sources instead:

```
docker-compose up
```

Or without Docker, point `etl/config.py` at a running Postgres instance and
run `python etl/run_all.py` from `etl/`.

**Requires raw source data that isn't in this repo.** `data/updated-sheng/`
(Sheng's combined schools export, Bob's NU org export, and the raw CRDC/EDFacts
assessment data) is gitignored — it's ~2.6 GB, well past what's reasonable to
version in git (a single CRDC file alone is 794 MB, and two EDFacts files are
938 MB and 875 MB, over GitHub's 100 MB per-file limit on their own). Get it
from the team's shared Drive folder:
[data (Google Drive)](https://drive.google.com/drive/folders/1H0_L1gA-ND8acU7Ux1VC9PIDyH0svpJ9?usp=sharing) —
request access from Max if you can't see it. Download it into `data/updated-sheng/`
before running `docker-compose up` or `etl/run_all.py`.

`tests/test_docker_pipeline.py` auto-skips if this data isn't present locally,
so the test suite still runs (see [`docs/TEST_PLAN.md`](docs/TEST_PLAN.md))
without it.

## Docs

- [`docs/EDA.md`](docs/EDA.md) — source inventory, join keys, profiling
- [`docs/EDA_NCES_private_EN.md`](docs/EDA_NCES_private_EN.md) — NCES private-school EDA
- [`docs/BOB_BRIEFING.md`](docs/BOB_BRIEFING.md) — database overview and open data gaps
- [`data/NU-Master/README.md`](data/NU-Master/README.md) — what's needed for the CEEB crosswalk
