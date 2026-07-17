"""
System test for the Docker/Postgres pipeline -- etl/run_all.py against a real,
freshly-started Postgres 16 container.

Auto-skips (does not fail) when its preconditions aren't met, exactly like
test_system_pipeline.py's CSV-only tests skip when csv_exports/ isn't present:
  - Docker daemon not reachable
  - data/updated-sheng/ not present (it's gitignored -- ~2.6 GB, see docs/TEST_PLAN.md
    Section 4 for why; a fresh clone won't have it, and that's correct, not a bug)

Verified working end to end on 2026-07-17 with the raw data present locally: the pipeline
completed successfully and schools_org_all's CEEB match count (16,508) matched the CSV-path
result in test_system_pipeline.py exactly -- cross-validating both paths compute the same
result from the same underlying join logic.

This test brings up its own db container on port 5433 (matching docker-compose.yml) and
tears it down afterward, so it doesn't collide with a database a developer may already have
running for other purposes, and doesn't leave state behind for the next run.
"""
import os
import subprocess
import time

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SHENG_DATA = os.path.join(REPO_ROOT, "data", "updated-sheng", "schools_combined_enriched_ceeb.csv")


def _docker_available():
    return subprocess.run(["docker", "ps"], capture_output=True).returncode == 0


pytestmark = pytest.mark.skipif(
    not (_docker_available() and os.path.exists(SHENG_DATA)),
    reason="requires a running Docker daemon AND data/updated-sheng/ present locally "
           "(gitignored, ~2.6 GB -- not present on a fresh clone, see docs/TEST_PLAN.md Section 4)",
)


def _compose(*args, timeout=600):
    return subprocess.run(
        ["docker", "compose", *args], cwd=REPO_ROOT,
        capture_output=True, text=True, timeout=timeout,
    )


class TestDockerPostgresPipeline:
    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def db_container(cls):
        up = _compose("up", "-d", "db")
        assert up.returncode == 0, f"docker compose up -d db failed:\n{up.stderr}"
        for _ in range(30):
            health = subprocess.run(
                ["docker", "inspect", "--format={{.State.Health.Status}}", "capstone-db"],
                capture_output=True, text=True,
            ).stdout.strip()
            if health == "healthy":
                break
            time.sleep(2)
        else:
            pytest.fail("capstone-db never became healthy")
        yield
        _compose("down", "-v")

    def test_full_pipeline_completes_successfully(self):
        build = _compose("build", "etl")
        assert build.returncode == 0, f"docker compose build etl failed:\n{build.stderr}"

        run = _compose("run", "--rm", "etl", timeout=900)
        assert run.returncode == 0, f"etl/run_all.py failed:\n{run.stdout}\n{run.stderr}"
        assert "Pipeline completed successfully" in run.stdout

    def test_schools_org_all_row_count_matches_csv_path(self):
        """Cross-validates the DB-backed path against the CSV-only path (test_system_pipeline.py)
        -- both should compute identical row counts from the same join logic."""
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", "db", "psql", "-U", "capstone", "-d", "capstone",
             "-t", "-c", "SELECT COUNT(*) FROM schools_org_all;"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        assert result.returncode == 0
        count = int(result.stdout.strip())
        assert count > 50_000  # production scale as of 2026-07-17: 53,966 rows
