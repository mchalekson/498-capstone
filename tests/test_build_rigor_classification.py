"""Unit tests for etl/build_rigor_classification.py's core math (z-scoring, proportional
weight reallocation for missing components, quintile tier assignment)."""
import numpy as np
import pandas as pd

from build_rigor_classification import zscore, weighted_composite, assign_tiers


class TestZscore:
    def test_mean_zero_std_one(self):
        s = pd.Series([1, 2, 3, 4, 5])
        z = zscore(s)
        assert abs(z.mean()) < 1e-9
        assert abs(z.std() - 1) < 1e-9

    def test_constant_series_returns_all_nan(self):
        """Zero variance -> can't standardize -- must return NaN, not divide by zero."""
        s = pd.Series([5, 5, 5, 5])
        z = zscore(s)
        assert z.isna().all()

    def test_nan_passthrough(self):
        s = pd.Series([1, np.nan, 3])
        z = zscore(s)
        assert z.isna().iloc[1]
        assert not z.isna().iloc[0]


class TestWeightedComposite:
    def test_full_coverage_matches_simple_weighted_average(self):
        comp = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})
        weights = {"a": 0.5, "b": 0.5}
        score, avail = weighted_composite(comp, weights)
        assert score.iloc[0] == 2.0  # (1*0.5 + 3*0.5)/1.0
        assert score.iloc[1] == 3.0

    def test_missing_component_reallocates_weight_proportionally(self):
        """Regression test for the documented design: a school missing one component gets
        its score from the REMAINING components with weight renormalized to sum to 1, not
        imputed to 0 and not excluded outright."""
        comp = pd.DataFrame({"a": [1.0, np.nan], "b": [3.0, 4.0], "c": [5.0, 6.0]})
        weights = {"a": 0.5, "b": 0.25, "c": 0.25}
        score, avail = weighted_composite(comp, weights)
        # row 1: only b,c available, weights renormalized to 0.5/0.5
        expected_row1 = 4.0 * 0.5 + 6.0 * 0.5
        assert abs(score.iloc[1] - expected_row1) < 1e-9

    def test_no_components_available_yields_nan_not_zero(self):
        comp = pd.DataFrame({"a": [np.nan], "b": [np.nan]})
        weights = {"a": 0.5, "b": 0.5}
        score, avail = weighted_composite(comp, weights)
        assert score.isna().iloc[0]

    def test_zero_weight_component_never_influences_score(self):
        """ib has weight 0 in the default scheme -- its value must not move the composite
        even when present, since that's what makes 'IB excluded from rigor' actually true."""
        comp = pd.DataFrame({"ap": [1.0], "ib": [999.0]})
        weights = {"ap": 1.0, "ib": 0.0}
        score, avail = weighted_composite(comp, weights)
        assert score.iloc[0] == 1.0


class TestAssignTiers:
    def test_five_tiers_roughly_equal_size(self):
        score = pd.Series(range(100))
        labels, nums = assign_tiers(score)
        counts = nums.value_counts().sort_index()
        assert len(counts) == 5
        assert counts.min() >= 19  # 100/5 = 20, allow rounding slack

    def test_lowest_scores_get_below_average(self):
        score = pd.Series(range(100))
        labels, nums = assign_tiers(score)
        assert labels.iloc[0] == "Below Average"
        assert labels.iloc[99] == "Most Demanding"

    def test_all_nan_input_returns_all_nan(self):
        score = pd.Series([np.nan, np.nan])
        labels, nums = assign_tiers(score)
        assert labels.isna().all()
        assert nums.isna().all()

    def test_nan_scores_stay_untiered(self):
        score = pd.Series(list(range(20)) + [np.nan])
        labels, nums = assign_tiers(score)
        assert pd.isna(labels.iloc[-1])
