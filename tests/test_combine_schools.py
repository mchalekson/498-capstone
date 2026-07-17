"""
Unit tests for etl/combine_schools.py's resolve_ceeb_ties() -- the fix for the CEEB
fan-out bug documented in docs/EDA_features_joined.md 3b and docs/DATA_DICTIONARY.md.
"""
import numpy as np
import pandas as pd

from combine_schools import normalize_name, resolve_ceeb_ties


class TestNormalizeName:
    def test_saint_becomes_st(self):
        assert normalize_name("Saint Mary High School") == "ST MARY HIGH SCHOOL"

    def test_hs_abbreviation_expanded(self):
        assert normalize_name("Lincoln HS") == "LINCOLN HIGH SCHOOL"

    def test_nan_returns_empty_string(self):
        assert normalize_name(np.nan) == ""

    def test_punctuation_stripped(self):
        assert normalize_name("St. John's-Prep") == "ST JOHN S PREP"


class TestResolveCeebTies:
    def _schools(self):
        return pd.DataFrame([
            {"school_id": "A1", "school_name": "Vista High Continuation", "ceeb": "050222",
             "ceeb_matched_name": "Vista High Continuation", "ceeb_match_tier": "auto_accept"},
            {"school_id": "A2", "school_name": "Abraxas Continuation High", "ceeb": "050222",
             "ceeb_matched_name": "Vista High Continuation", "ceeb_match_tier": "review"},
            {"school_id": "A3", "school_name": "Unrelated School", "ceeb": "999999",
             "ceeb_matched_name": "Unrelated School", "ceeb_match_tier": "auto_accept"},
        ])

    def test_keeps_the_best_tier_match(self):
        """The auto_accept row (exact match to the crosswalk name) should keep the CEEB;
        the review-tier row (a different school, same CEEB) should lose it."""
        out = resolve_ceeb_ties(self._schools())
        kept = out[out["school_id"] == "A1"].iloc[0]
        lost = out[out["school_id"] == "A2"].iloc[0]
        assert kept["ceeb"] == "050222"
        assert pd.isna(lost["ceeb"])

    def test_flags_the_row_that_lost_its_ceeb(self):
        out = resolve_ceeb_ties(self._schools())
        assert out[out["school_id"] == "A2"].iloc[0]["ceeb_fanout_resolved"] == True  # noqa: E712
        assert out[out["school_id"] == "A1"].iloc[0]["ceeb_fanout_resolved"] == False  # noqa: E712

    def test_unique_ceeb_untouched(self):
        out = resolve_ceeb_ties(self._schools())
        row = out[out["school_id"] == "A3"].iloc[0]
        assert row["ceeb"] == "999999"
        assert row["ceeb_fanout_resolved"] == False  # noqa: E712

    def test_no_duplicates_returns_unmodified_frame(self):
        """When there's nothing to resolve, the function should be a no-op (aside from
        dropping its own working columns) -- must not crash on a frame with no fan-out."""
        schools = self._schools()
        no_dupes = schools[schools["school_id"] != "A2"].reset_index(drop=True)
        out = resolve_ceeb_ties(no_dupes)
        assert out["ceeb"].tolist() == no_dupes["ceeb"].tolist()

    def test_tie_break_prefers_exact_name_match_when_tier_is_equal(self):
        """Two review-tier rows sharing a CEEB: the one whose name exactly matches the
        crosswalk's matched name should be preferred over the one that doesn't."""
        schools = pd.DataFrame([
            {"school_id": "B1", "school_name": "Exact Match School", "ceeb": "111111",
             "ceeb_matched_name": "Exact Match School", "ceeb_match_tier": "review"},
            {"school_id": "B2", "school_name": "Some Other School", "ceeb": "111111",
             "ceeb_matched_name": "Exact Match School", "ceeb_match_tier": "review"},
        ])
        out = resolve_ceeb_ties(schools)
        assert out[out["school_id"] == "B1"].iloc[0]["ceeb"] == "111111"
        assert pd.isna(out[out["school_id"] == "B2"].iloc[0]["ceeb"])
