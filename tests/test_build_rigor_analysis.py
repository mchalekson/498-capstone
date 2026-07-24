"""
Unit tests for etl/build_rigor_analysis.py -- the AP-efficiency lens (Bob's Wk5
"low offering / high scores" idea). Locks in the quadrant assignment and the sign of the
efficiency signal so the "selective & effective" flag can't silently invert.
"""
import numpy as np
import pandas as pd

from build_rigor_analysis import ap_efficiency, SCORE_COL, OFFER_COL


def _frame(scores, offers):
    return pd.DataFrame({SCORE_COL: scores, OFFER_COL: offers})


class TestAPEfficiency:
    def test_quadrant_assignment(self):
        # scores rise 1..5, offerings fall 5..1 -> medians are 3 each
        df = _frame([1, 2, 3, 4, 5], [5, 4, 3, 2, 1])
        _, quad, n_both = ap_efficiency(df)
        assert n_both == 5
        # high score + low offering -> the Bob case
        assert quad.iloc[3].startswith("Selective & effective")
        assert quad.iloc[4].startswith("Selective & effective")
        # low score + high offering
        assert quad.iloc[0] == "Broad but underperforming"

    def test_efficiency_sign_and_ordering(self):
        df = _frame([1, 2, 3, 4, 5], [5, 4, 3, 2, 1])
        eff, _, _ = ap_efficiency(df)
        # highest score / lowest offering must be the most efficient; the inverse the least
        assert eff.iloc[4] > eff.iloc[0]
        assert eff.iloc[4] > 0 > eff.iloc[0]

    def test_missing_signal_is_unscored(self):
        # a school missing either signal gets no efficiency and no quadrant (not a default bucket)
        df = _frame([4.0, np.nan, 3.0], [np.nan, 10.0, 15.0])
        eff, quad, n_both = ap_efficiency(df)
        assert n_both == 1                 # only the third row has both
        assert pd.isna(eff.iloc[0]) and pd.isna(eff.iloc[1])
        assert pd.isna(quad.iloc[0]) and pd.isna(quad.iloc[1])
