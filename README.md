# 498-capstone

ETL pipeline that loads NCES, Census, NAEP, ISBE, IB, CPS, and College Board
data into a Postgres database and combines it into school-level enriched
tables.

## Quickstart

```
docker-compose up
```

Or without Docker, point `etl/config.py` at a running Postgres instance and
run `python etl/run_all.py` from `etl/`.

Every table and view is also exported to CSV in [`csv_exports/`](csv_exports/)
for direct access without running the pipeline.

## Docs

- [`docs/EDA.md`](docs/EDA.md) — source inventory, join keys, profiling
- [`docs/EDA_NCES_private_EN.md`](docs/EDA_NCES_private_EN.md) — NCES private-school EDA
- [`docs/BOB_BRIEFING.md`](docs/BOB_BRIEFING.md) — database overview and open data gaps
- [`data/NU-Master/README.md`](data/NU-Master/README.md) — what's needed for the CEEB crosswalk
