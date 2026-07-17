"""
System test: runs the real end-to-end pipeline (build_features -> build_modeling_dataset ->
build_rigor_classification -> build_clustering -> build_benchmarking) against the actual
exported CSVs and asserts each stage completes and produces output in the expected shape.

Skipped automatically if csv_exports/ isn't present (e.g. a fresh clone without the data
checked out, or a CI runner that doesn't have it) -- this is a system test over real data,
not something that should be faked with a fixture.
"""
import os
import subprocess
import sys

import pandas as pd
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CSV_EXPORTS = os.path.join(REPO_ROOT, "csv_exports")
ETL_DIR = os.path.join(REPO_ROOT, "etl")

pytestmark = pytest.mark.skipif(
    not os.path.exists(os.path.join(CSV_EXPORTS, "schools_org_all.csv")),
    reason="csv_exports/schools_org_all.csv not present -- system test needs the real exported data",
)


def _run(script, *args):
    result = subprocess.run(
        [sys.executable, os.path.join(ETL_DIR, script), *args],
        cwd=CSV_EXPORTS, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, f"{script} failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    return result


class TestFullPipelineRunsCleanly:
    def test_build_features(self):
        _run("build_features.py", "schools_org_all.csv")
        out = pd.read_csv(os.path.join(CSV_EXPORTS, "schools_features.csv"), low_memory=False)
        assert len(out) > 50_000  # production scale as of 2026-07-17: 53,966 rows
        assert "sector" in out.columns
        assert out["sector"].isin(["public", "private", "other/oos"]).all()

    def test_build_modeling_dataset(self):
        _run("build_modeling_dataset.py", "schools_features.csv", "--version", "v1")
        matches = [f for f in os.listdir(CSV_EXPORTS) if f.startswith("modeling_dataset_v1_")]
        assert matches, "no modeling_dataset_v1_*.csv produced"
        out = pd.read_csv(os.path.join(CSV_EXPORTS, sorted(matches)[-1]), low_memory=False)
        assert out["sector"].isin(["public", "private"]).all()  # other/oos must be gone
        assert (out["enrollment_9_12"].isna() | (out["enrollment_9_12"] >= 30)).all()

    def test_build_rigor_classification(self):
        matches = sorted(f for f in os.listdir(CSV_EXPORTS) if f.startswith("modeling_dataset_v1_"))
        _run("build_rigor_classification.py", matches[-1], "--version", "v1")
        rc_matches = [f for f in os.listdir(CSV_EXPORTS) if f.startswith("rigor_classification_v1_")]
        assert rc_matches
        out = pd.read_csv(os.path.join(CSV_EXPORTS, sorted(rc_matches)[-1]), low_memory=False)
        assert "rigor_tier_label" in out.columns
        valid_tiers = {"Below Average", "Average", "Demanding", "Very Demanding", "Most Demanding"}
        assert set(out["rigor_tier_label"].dropna().unique()) <= valid_tiers

    def test_build_clustering(self):
        rc_matches = sorted(f for f in os.listdir(CSV_EXPORTS) if f.startswith("rigor_classification_v1_"))
        _run("build_clustering.py", rc_matches[-1], "--version", "v1", "--k-min", "2", "--k-max", "4")
        cl_matches = [f for f in os.listdir(CSV_EXPORTS) if f.startswith("clustering_v1_")]
        assert cl_matches
        out = pd.read_csv(os.path.join(CSV_EXPORTS, sorted(cl_matches)[-1]), low_memory=False)
        assert "cluster_kmeans" in out.columns

    def test_build_benchmarking(self):
        rc_matches = sorted(f for f in os.listdir(CSV_EXPORTS) if f.startswith("rigor_classification_v1_"))
        _run("build_benchmarking.py", rc_matches[-1], "--version", "v1")
        bm_matches = [f for f in os.listdir(CSV_EXPORTS) if f.startswith("benchmarking_v1_")]
        assert bm_matches
