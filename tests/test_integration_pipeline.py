"""
Integration tests: verify build_features.build() and build_modeling_dataset's freeze
functions compose correctly end to end, on a small synthetic fixture -- catches bugs that
only show up when steps are chained (e.g. a column one step renames/drops that the next
step still expects), which the per-function unit tests can't see on their own.
"""
import pandas as pd

from build_features import build
from build_modeling_dataset import apply_min_size_freeze, restrict_to_hs_universe


class TestFeaturesIntoModelingDatasetFreeze:
    def test_full_chain_on_fixture(self, tiny_schools_org_all):
        feats = build(tiny_schools_org_all)
        frozen = restrict_to_hs_universe(feats)
        frozen = apply_min_size_freeze(frozen)

        # only public/private HS survive the universe restriction (org-only row dropped)
        assert set(frozen["sector"].unique()) <= {"public", "private"}
        # every surviving row is public XOR private, never both, never neither
        assert (frozen["is_public_hs"] ^ frozen["is_private_hs"]).all()
        # the private-HS-via-pss_id-only row (the sector-classification regression case)
        # must have survived into the frozen output, not been silently dropped
        assert "Private HS B" in frozen["school_name"].values

    def test_frozen_output_has_no_duplicate_school_names_from_fixture(self, tiny_schools_org_all):
        """Sanity check specific to this fixture: each row is a distinct school, so the
        frozen output should never duplicate a school_name -- a stand-in for the kind of
        row-fanout bug the real CEEB fan-out issue caused in production."""
        feats = build(tiny_schools_org_all)
        frozen = restrict_to_hs_universe(feats)
        names = frozen["school_name"].dropna()
        assert names.is_unique
