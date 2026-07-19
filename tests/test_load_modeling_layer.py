"""Unit tests for etl/load_modeling_layer.py -- freeze resolution and frame tidying.

These are deliberately DB-free. The actual to_sql load is covered by the Docker/Postgres
system test (which auto-skips without the raw data); what's testable and worth testing
here is the part with real logic in it: resolving which frozen CSV each table comes from,
and normalizing the frames before they hit Postgres.

The freeze-drift tests below are the important ones. tests/test_system_pipeline.py re-runs
the real build scripts against the real csv_exports/ directory, so simply running the test
suite writes `*_v1_<today>.csv` files alongside the committed freeze -- with a narrower
clustering k-sweep, so they differ in substance, not just in date. An earlier version of
this loader pinned on the version only and took the newest match, which meant `pytest`
could silently redefine which dataset the database considered frozen.
"""
import os

import pandas as pd
import pytest

import load_modeling_layer as lml

TAG = lml.FREEZE_TAG


@pytest.fixture
def fake_exports(tmp_path):
    """A csv_exports/ stand-in holding exactly the pinned freeze."""
    for stem in lml.DATED_ARTIFACTS.values():
        (tmp_path / f"{stem}_{TAG}.csv").write_text("a,b\n1,2\n")
    for filename in lml.UNDATED_ARTIFACTS.values():
        (tmp_path / filename).write_text("variable,description\nceeb,CEEB code\n")
    return tmp_path


class TestResolveArtifacts:
    def test_resolves_every_expected_artifact(self, fake_exports):
        resolved = lml.resolve_artifacts(csv_dir=str(fake_exports))
        expected = set(lml.DATED_ARTIFACTS) | set(lml.UNDATED_ARTIFACTS)
        assert set(resolved) == expected
        assert all(p is not None for p in resolved.values())

    def test_missing_artifact_resolves_to_none_not_error(self, tmp_path):
        """A fresh clone that has only run stages 1-5 has no modeling layer. That must
        resolve to None so the stage can skip, not raise and fail the whole pipeline."""
        resolved = lml.resolve_artifacts(csv_dir=str(tmp_path))
        assert all(p is None for p in resolved.values())

    def test_selects_a_requested_tag(self, fake_exports):
        (fake_exports / "modeling_dataset_v2_2026-08-01.csv").write_text("a,b\n9,9\n")
        resolved = lml.resolve_artifacts(tag="v2_2026-08-01", csv_dir=str(fake_exports))
        assert resolved["modeling_dataset"].endswith("modeling_dataset_v2_2026-08-01.csv")
        # v2 exists only for modeling_dataset here; the rest must be None, not silently
        # fall back to their v1 files.
        assert resolved["rigor_classification"] is None


class TestFreezeDoesNotDrift:
    def test_newer_file_at_same_version_is_ignored(self, fake_exports):
        """The regression this file exists for: `pytest tests/` writes v1 artifacts dated
        today next to the committed freeze. A newer date at the same version must NOT win."""
        (fake_exports / "modeling_dataset_v1_2099-01-01.csv").write_text("a,b\n9,9\n")
        resolved = lml.resolve_artifacts(csv_dir=str(fake_exports))
        assert resolved["modeling_dataset"].endswith(f"modeling_dataset_{TAG}.csv")

    def test_higher_version_is_ignored_while_pinned(self, fake_exports):
        (fake_exports / "modeling_dataset_v9_2099-01-01.csv").write_text("a,b\n9,9\n")
        resolved = lml.resolve_artifacts(csv_dir=str(fake_exports))
        assert resolved["modeling_dataset"].endswith(f"modeling_dataset_{TAG}.csv")

    def test_no_fallback_when_pinned_file_absent(self, tmp_path):
        """If the pinned file is gone, resolve to None -- never to a neighbouring build."""
        (tmp_path / "modeling_dataset_v1_2026-07-18.csv").write_text("a,b\n9,9\n")
        resolved = lml.resolve_artifacts(csv_dir=str(tmp_path))
        assert resolved["modeling_dataset"] is None

    def test_find_stray_builds_reports_non_freeze_artifacts(self, fake_exports):
        (fake_exports / "clustering_v1_2099-01-01.csv").write_text("a,b\n9,9\n")
        (fake_exports / "gap_statistic_v1_2099-01-01.csv").write_text("a,b\n9,9\n")
        stray = [os.path.basename(p) for p in lml.find_stray_builds(csv_dir=str(fake_exports))]
        assert sorted(stray) == ["clustering_v1_2099-01-01.csv", "gap_statistic_v1_2099-01-01.csv"]

    def test_find_stray_builds_clean_when_only_freeze_present(self, fake_exports):
        assert lml.find_stray_builds(csv_dir=str(fake_exports)) == []


class TestTidy:
    def test_names_the_pca_loadings_index_column(self):
        """pca_loadings is written with the feature name in a nameless index column.
        Postgres can't take an empty column name, so it must become 'feature'."""
        df = pd.DataFrame({"": ["latitude", "funding"], "PC1": [0.47, 0.66]})
        out = lml._tidy(df, "pca_loadings")
        assert "feature" in out.columns
        assert out["feature"].tolist() == ["latitude", "funding"]

    def test_handles_pandas_unnamed_index_column(self):
        df = pd.DataFrame({"Unnamed: 0": ["ap"], "PC1": [0.21]})
        out = lml._tidy(df, "pca_loadings")
        assert "feature" in out.columns

    def test_normalizes_headers_to_snake_case(self):
        df = pd.DataFrame({"Rigor Tier Label": ["Demanding"], "AP": [1]})
        out = lml._tidy(df, "rigor_classification")
        assert list(out.columns) == ["rigor_tier_label", "ap"]

    def test_leaves_already_clean_headers_alone(self):
        df = pd.DataFrame({"ceeb": ["000049"], "rigor_score": [0.5]})
        out = lml._tidy(df, "modeling_dataset")
        assert list(out.columns) == ["ceeb", "rigor_score"]


class TestPinnedFreezeIsOnDisk:
    def test_real_exports_dir_resolves_the_documented_freeze(self):
        """Guards the actual repo state: the pinned freeze must still be on disk. If someone
        deletes or renames it, this fails here rather than at pipeline runtime."""
        if not os.path.isdir(lml.CSV_EXPORTS_DIR):
            pytest.skip("csv_exports/ not present")
        resolved = lml.resolve_artifacts()
        missing = [t for t, p in resolved.items() if p is None]
        assert not missing, f"pinned freeze {TAG} missing artifacts: {missing}"
