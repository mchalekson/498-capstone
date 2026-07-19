"""
System test: runs the real end-to-end pipeline (build_features -> build_modeling_dataset ->
build_rigor_classification -> build_clustering -> build_benchmarking) against the actual
exported CSVs and asserts each stage completes and produces output in the expected shape.

Skipped automatically if csv_exports/ isn't present (e.g. a fresh clone without the data
checked out, or a CI runner that doesn't have it) -- this is a system test over real data,
not something that should be faked with a fixture.

Isolation: the chain runs in a temp directory, NOT in csv_exports/. It used to run in
csv_exports/ directly, which meant `pytest tests/` wrote fresh `*_v1_<today>.csv` artifacts
next to the committed freeze on every run -- and since this test deliberately uses a
narrower clustering sweep (--k-max 4) for speed, those files differed from the freeze in
substance, not just in date. Anything resolving artifacts by "newest match" would then pick
up test output as if it were the frozen dataset (see etl/load_modeling_layer.py's
FREEZE_TAG). Real inputs are symlinked in rather than copied: schools_org_all.csv alone is
~27 MB and the test only reads it.

The chain also runs once per session rather than once per test. Each stage consumes the
previous stage's output, so running them as five independent tests made the suite
order-dependent -- and made each test's "find the newest matching file" lookup ambiguous
whenever a real build already sat in the same directory.
"""
import glob
import os
import subprocess
import sys

import pandas as pd
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CSV_EXPORTS = os.path.join(REPO_ROOT, "csv_exports")
ETL_DIR = os.path.join(REPO_ROOT, "etl")

# What build_features.py needs to find next to its input file: the joined table itself,
# the two Census inputs for the Goal 4 funding join, and the IB directory. It degrades
# gracefully without the latter three, but then the test wouldn't exercise those paths.
REQUIRED_INPUTS = [
    "schools_org_all.csv",
    "census_school_finances_clean.csv",
    "census_saipe_poverty_clean.csv",
    "ib_schools.csv",
]

pytestmark = pytest.mark.skipif(
    not os.path.exists(os.path.join(CSV_EXPORTS, "schools_org_all.csv")),
    reason="csv_exports/schools_org_all.csv not present -- system test needs the real exported data",
)

TEST_VERSION = "systest"


def _run(script, *args, cwd):
    result = subprocess.run(
        [sys.executable, os.path.join(ETL_DIR, script), *args],
        cwd=cwd, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, f"{script} failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    return result


def _only(workdir, stem):
    """The single artifact for a stem in the isolated workdir.

    Asserts uniqueness rather than taking the newest: in a directory this test owns, more
    than one match means a stage ran twice, which is a bug worth failing on -- not
    something to silently disambiguate by date.
    """
    matches = sorted(glob.glob(os.path.join(workdir, f"{stem}_{TEST_VERSION}_*.csv")))
    assert matches, f"no {stem}_{TEST_VERSION}_*.csv produced in {workdir}"
    assert len(matches) == 1, f"expected exactly one {stem} artifact, got {matches}"
    return matches[0]


@pytest.fixture(scope="session")
def pipeline_run(tmp_path_factory):
    """Run the full build chain once, in an isolated directory, and hand back its path."""
    workdir = tmp_path_factory.mktemp("system_pipeline")

    for name in REQUIRED_INPUTS:
        src = os.path.join(CSV_EXPORTS, name)
        if not os.path.exists(src):
            pytest.skip(f"csv_exports/{name} not present -- system test needs the real exported data")
        # build_features.py resolves its sibling inputs via os.path.abspath (which does not
        # follow symlinks), so symlinked inputs still resolve to this workdir, not back to
        # csv_exports/. That's what keeps the outputs isolated.
        os.symlink(src, workdir / name)

    args = ["--version", TEST_VERSION, "--outdir", str(workdir)]

    # build_features.py hardcodes its output to the current working directory, so it must
    # run with cwd=workdir; the rest honour --outdir.
    _run("build_features.py", "schools_org_all.csv", cwd=str(workdir))
    _run("build_modeling_dataset.py", "schools_features.csv", *args, cwd=str(workdir))

    modeling = _only(str(workdir), "modeling_dataset")
    _run("build_rigor_classification.py", modeling, *args, cwd=str(workdir))

    rigor = _only(str(workdir), "rigor_classification")
    # Narrower k-sweep than the real build (which goes to 8) purely to keep the suite fast.
    _run("build_clustering.py", rigor, *args, "--k-min", "2", "--k-max", "4", cwd=str(workdir))
    _run("build_benchmarking.py", rigor, *args, cwd=str(workdir))

    return str(workdir)


class TestFullPipelineRunsCleanly:
    def test_build_features(self, pipeline_run):
        out = pd.read_csv(os.path.join(pipeline_run, "schools_features.csv"), low_memory=False)
        assert len(out) > 50_000  # production scale as of 2026-07-17: 53,966 rows
        assert "sector" in out.columns
        assert out["sector"].isin(["public", "private", "other/oos"]).all()

    def test_build_modeling_dataset(self, pipeline_run):
        out = pd.read_csv(_only(pipeline_run, "modeling_dataset"), low_memory=False)
        assert out["sector"].isin(["public", "private"]).all()  # other/oos must be gone
        assert (out["enrollment_9_12"].isna() | (out["enrollment_9_12"] >= 30)).all()

    def test_build_rigor_classification(self, pipeline_run):
        out = pd.read_csv(_only(pipeline_run, "rigor_classification"), low_memory=False)
        assert "rigor_tier_label" in out.columns
        valid_tiers = {"Below Average", "Average", "Demanding", "Very Demanding", "Most Demanding"}
        assert set(out["rigor_tier_label"].dropna().unique()) <= valid_tiers

    def test_build_clustering(self, pipeline_run):
        out = pd.read_csv(_only(pipeline_run, "clustering"), low_memory=False)
        assert "cluster_kmeans" in out.columns

    def test_build_benchmarking(self, pipeline_run):
        out = pd.read_csv(_only(pipeline_run, "benchmarking"), low_memory=False)
        assert len(out) > 0


class TestLeavesTheRepoAlone:
    """The regression that motivated the isolation: this suite must not write build
    artifacts into csv_exports/, or it silently competes with the committed freeze."""

    def test_no_artifacts_written_to_csv_exports(self, pipeline_run):
        strays = glob.glob(os.path.join(CSV_EXPORTS, f"*_{TEST_VERSION}_*.csv"))
        assert not strays, f"system test wrote into csv_exports/: {strays}"

    def test_outputs_landed_in_the_isolated_workdir(self, pipeline_run):
        produced = glob.glob(os.path.join(pipeline_run, f"*_{TEST_VERSION}_*.csv"))
        assert len(produced) >= 5, f"expected the chain's artifacts in {pipeline_run}, got {produced}"
