"""Unit tests for etl/build_modeling_dataset.py -- the cleaning-freeze rules."""
import numpy as np
import pandas as pd

from build_modeling_dataset import (
    apply_min_size_freeze,
    apply_sentinel_scrub,
    restrict_to_hs_universe,
    MIN_ENROLLMENT_9_12,
)


class TestMinSizeFreeze:
    def test_drops_below_threshold(self):
        df = pd.DataFrame({"enrollment_9_12": [10, 29, 30, 100]})
        out = apply_min_size_freeze(df)
        assert sorted(out["enrollment_9_12"].tolist()) == [30, 100]

    def test_keeps_unknown_enrollment(self):
        """Missing enrollment_9_12 means 'we don't know', not 'too small' -- must be kept,
        not dropped by a NaN < 30 comparison silently evaluating False in a filter."""
        df = pd.DataFrame({"enrollment_9_12": [np.nan, 5]})
        out = apply_min_size_freeze(df)
        assert len(out) == 1
        assert pd.isna(out["enrollment_9_12"].iloc[0])

    def test_boundary_is_inclusive(self):
        df = pd.DataFrame({"enrollment_9_12": [MIN_ENROLLMENT_9_12]})
        out = apply_min_size_freeze(df)
        assert len(out) == 1


class TestRestrictToHsUniverse:
    def test_drops_other_oos(self):
        df = pd.DataFrame({
            "is_public_hs": [True, False, False],
            "is_private_hs": [False, True, False],
        })
        out = restrict_to_hs_universe(df)
        assert len(out) == 2


class TestSentinelScrub:
    def test_negative_sentinel_in_rate_column_becomes_nan(self):
        df = pd.DataFrame({"ap_participation_rate": [0.5, -1, 0.3]})
        out = apply_sentinel_scrub(df)
        assert out["ap_participation_rate"].isna().sum() == 1

    def test_legitimate_zero_is_not_touched(self):
        """0 AP classes offered is a real value, not a sentinel -- only the specific
        SENTINEL_VALUES set should be scrubbed, not zero itself."""
        df = pd.DataFrame({"grad_rate_score": [0, 50, 100]})
        out = apply_sentinel_scrub(df)
        assert out["grad_rate_score"].isna().sum() == 0

    def test_non_suspect_column_name_untouched(self):
        """Columns without a rate/pct/score/etc keyword in the name are not scrubbed, even
        if they contain a value that would be a sentinel elsewhere -- avoids clobbering a
        school that legitimately has -1 of something unrelated to suppression codes."""
        df = pd.DataFrame({"some_raw_count": [-1, 5]})
        out = apply_sentinel_scrub(df)
        assert out["some_raw_count"].iloc[0] == -1
