"""
Unit tests for etl/build_features.py.

Several of these encode bugs that were actually found and fixed during development
(see docs/EDA_features_joined.md and docs/BOB_BRIEFING.md's update logs) -- they exist
specifically so those bugs cannot silently come back:
  - is_private_hs used to require school_id to be null, which dropped every private
    school with a school-side (pss_id) record into "other/oos" (test_is_private_hs_*).
  - ib_flag_candidate used to count 'reject'-tier matches as confirmed IB schools
    (test_ib_flag_candidate_gating).
  - leaid used to come from a 5-char column with a 0% match rate against Census finance
    data instead of nces_id_12[:7] (test_leaid_derivation).
"""
import numpy as np
import pandas as pd
import pytest

from build_features import parse_bucket_midpoint, winsorize, build


class TestParseBucketMidpoint:
    def test_simple_range(self):
        assert parse_bucket_midpoint("26% - 50%") == 38.0

    def test_narrow_range_no_percent(self):
        assert parse_bucket_midpoint("06 -10") == 8.0

    def test_or_more_under_100(self):
        """Regression test: build_features.py's own docstring claimed this returns 24
        (a stale typo), but the actual code computes 20 + 5 = 25, consistent with the
        function's other examples ('90% or more' -> 90 + 5 = 95). Fixed the docstring,
        not the code -- 25 is the correct, consistent answer."""
        assert parse_bucket_midpoint("greater than 20") == 25.0

    def test_or_more_under_100_percent(self):
        assert parse_bucket_midpoint("90% or more") == 95.0  # 90 + 5 (n < 100 branch)

    def test_or_more_over_100(self):
        assert parse_bucket_midpoint("More than 1000") == 1200.0  # 1000 * 1.2

    def test_or_fewer(self):
        assert parse_bucket_midpoint("10% or fewer") == 5.0

    def test_bare_number(self):
        assert parse_bucket_midpoint("0") == 0.0

    def test_nan_input(self):
        assert pd.isna(parse_bucket_midpoint(np.nan))

    def test_unparseable_string(self):
        assert pd.isna(parse_bucket_midpoint("Not Applicable"))


class TestWinsorize:
    def test_clips_extreme_values(self):
        s = pd.Series(list(range(1, 100)) + [10000])  # one huge outlier
        out = winsorize(s)
        assert out.max() < 10000  # the outlier got clipped
        assert out.min() >= 1

    def test_all_nan_does_not_crash(self):
        s = pd.Series([np.nan, np.nan, np.nan])
        out = winsorize(s)
        assert pd.isna(out).all()


class TestBuildSectorClassification:
    def test_is_public_hs(self, tiny_schools_org_all):
        feats = build(tiny_schools_org_all)
        assert feats.loc[0, "is_public_hs"] == True  # noqa: E712
        assert feats.loc[0, "sector"] == "public"

    def test_is_private_hs_via_pss_id_only(self, tiny_schools_org_all):
        """Regression test: Private HS B has pss_id set but nu_type is null. The old logic
        (school_id.isna() & nu_type.isin([...])) required school_id to be null, so this row
        -- which HAS a school_id -- fell through to 'other/oos'. Must classify as private."""
        feats = build(tiny_schools_org_all)
        assert feats.loc[1, "is_private_hs"] == True  # noqa: E712
        assert feats.loc[1, "sector"] == "private"

    def test_is_private_hs_via_nu_type(self, tiny_schools_org_all):
        feats = build(tiny_schools_org_all)
        assert feats.loc[2, "is_private_hs"] == True  # noqa: E712
        assert feats.loc[2, "sector"] == "private"

    def test_org_only_row_is_other_oos(self, tiny_schools_org_all):
        feats = build(tiny_schools_org_all)
        assert feats.loc[3, "sector"] == "other/oos"

    def test_public_and_private_are_mutually_exclusive(self, tiny_schools_org_all):
        feats = build(tiny_schools_org_all)
        assert not (feats["is_public_hs"] & feats["is_private_hs"]).any()


class TestIBFlagGating:
    def test_review_tier_counts_as_candidate(self, tiny_schools_org_all):
        feats = build(tiny_schools_org_all)
        assert feats.loc[1, "ib_flag_candidate"] == 1

    def test_reject_tier_does_not_count(self, tiny_schools_org_all):
        """Regression test: the old ib_flag = ib_school_id.notna() counted 'reject'-tier
        matches (766 real rows in production) as confirmed IB schools. Row 2 has an
        ib_school_id set but tier='reject' -- must NOT be flagged."""
        feats = build(tiny_schools_org_all)
        assert feats.loc[2, "ib_flag_candidate"] == 0

    def test_no_ib_match_is_zero_not_null(self, tiny_schools_org_all):
        feats = build(tiny_schools_org_all)
        assert feats.loc[0, "ib_flag_candidate"] == 0


class TestLeaidDerivation:
    def test_leaid_is_first_seven_of_nces_id_12(self, tiny_schools_org_all):
        """Regression test: leaid must come from nces_id_12[:7], not the 5-char 'leaid'
        column shipped in schools_org_all (which had a 0% match rate against Census finance
        data in production -- see docs/EDA_features_joined.md)."""
        feats = build(tiny_schools_org_all)
        assert feats.loc[0, "leaid"] == "1700010"  # nces_id_12="170001000001"[:7]

    def test_leaid_is_null_without_nces_id_12(self, tiny_schools_org_all):
        feats = build(tiny_schools_org_all)
        assert pd.isna(feats.loc[1, "leaid"])


class TestAPPerformanceFeatures:
    """Wk5: AP *exam performance* + offered-vs-taken take-rate were added because the model
    was availability-only, which the literature (Geiser & Santelices) and the client both
    flagged as the weak signal. These lock in that the new columns compute correctly."""

    def test_ap_score_passed_through(self, tiny_schools_org_all):
        feats = build(tiny_schools_org_all)
        assert feats.loc[0, "ap_score_nu"] == 3.5
        assert feats.loc[1, "ap_score_nu"] == 2.8

    def test_ap_take_rate_is_taken_over_offered(self, tiny_schools_org_all):
        feats = build(tiny_schools_org_all)
        # public HS A: 2.5 tests taken / 15 offered; private HS B: 1.0 / 10.
        # abs tolerance because build() winsorizes (1/99 pct), which nudges values slightly
        # when there are only two non-null points in the fixture.
        assert feats.loc[0, "ap_take_rate"] == pytest.approx(2.5 / 15, abs=1e-2)
        assert feats.loc[1, "ap_take_rate"] == pytest.approx(1.0 / 10, abs=1e-2)
        assert feats.loc[0, "ap_take_rate"] > feats.loc[1, "ap_take_rate"]  # ordering preserved

    def test_ap_take_rate_null_when_offered_missing(self, tiny_schools_org_all):
        feats = build(tiny_schools_org_all)
        # row 2 has no offered value -> no take-rate (not a divide-by-zero or 0)
        assert pd.isna(feats.loc[2, "ap_take_rate"])

    def test_act_composite_absent_when_no_act_columns(self, tiny_schools_org_all):
        """ACT is ISBE-sourced (optional); build must not crash or invent it when absent."""
        feats = build(tiny_schools_org_all)
        assert "act_composite_il" not in feats.columns
