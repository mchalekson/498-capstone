# Rigor dashboard (Streamlit)

An interactive view over the frozen **v4** modeling layer. It reads the newest
`csv_exports/*_v4_*.csv` (so a re-dated rebuild is picked up automatically) and imports the
pipeline's own scoring functions from `etl/build_rigor_classification.py`, so the rigor explorer
reproduces the pipeline exactly rather than reimplementing it.

## Run

```bash
pip install -r dashboard/requirements.txt
cd dashboard && streamlit run app.py
```

Then open http://localhost:8501.

## Pages

| Page | What it shows |
|---|---|
| **Overview** | universe size, rigor-tier mix, NU-match counts, public/private coverage |
| **Rigor explorer** | move the six component weights + cut method; tiers recompute live, with Spearman vs. the shipped "designed" scheme, % of schools that change tier, nominal-vs-effective weights, and the SES-ordering check. A *what-if* tool — it never rewrites a file |
| **Clustering** | complete-case k-means: PCA projection, cluster sizes, gap statistic, and interpretable **cluster profiles** (`build_cluster_profiles.py`) |
| **Benchmarking** | a school's SAT percentile within its peer group (region / funding tier / rigor tier) |
| **Crosswalk & junctions** | CEEB↔NCES/IB/ISBE/CPS match rates + OPE↔CEEB junction status |
| **School lookup** | search any school; see its tier, score, cluster, and feature values |

## Data dependency

Requires the v4 modeling-layer CSVs in `../csv_exports` (produced by
`etl/run_modeling_layer.py --version v4` + `build_cluster_profiles.py`). If they're missing the
app shows a clear error rather than crashing.
