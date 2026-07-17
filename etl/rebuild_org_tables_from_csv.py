"""
rebuild_org_tables_from_csv.py — regenerate schools_org_enriched / schools_org_all
directly from the exported CSVs, with the CEEB fan-out fix applied.

Reuses combine_schools.py's resolve_ceeb_ties() and the exact same merge logic
as build_schools_org_enriched()/build_schools_org_all(), just reading/writing
CSVs instead of a live Postgres table -- for anyone without DB access who still
needs the corrected tables (see resolve_ceeb_ties() docstring in
combine_schools.py for why this fix exists).

Once someone reruns the real pipeline (etl/combine_schools.py) against a
populated DB, these CSVs should be regenerated from there instead -- this
script is a stand-in, not a replacement for that path.

Run from csv_exports/:  python ../etl/rebuild_org_tables_from_csv.py
"""
import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from combine_schools import resolve_ceeb_ties  # noqa: E402


def rebuild(schools_path, org_path):
    schools = pd.read_csv(schools_path, low_memory=False, dtype={"ceeb": str, "school_id": str})
    org = pd.read_csv(org_path, low_memory=False, dtype={"ceeb": str})

    schools = resolve_ceeb_ties(schools)
    org = org[org["ceeb"].notna()].add_prefix("nu_")

    enriched = schools.merge(org, left_on="ceeb", right_on="nu_ceeb", how="left")
    matched = enriched["nu_guid"].notna().sum()
    print(f"  schools_org_enriched: CEEB match {matched:,}/{len(enriched):,}")

    all_df = schools.merge(org, left_on="ceeb", right_on="nu_ceeb", how="outer")
    all_df["ceeb"] = all_df["ceeb"].fillna(all_df["nu_ceeb"])
    both = int((all_df["school_id"].notna() & all_df["nu_guid"].notna()).sum())
    school_only = int((all_df["school_id"].notna() & all_df["nu_guid"].isna()).sum())
    org_only = int((all_df["school_id"].isna() & all_df["nu_guid"].notna()).sum())
    print(f"  schools_org_all: {both:,} matched both sides, {school_only:,} school-only, "
          f"{org_only:,} NU-org-only ({len(all_df):,} total)")

    dup_orgs = all_df["nu_guid"].dropna()
    dups = len(dup_orgs) - dup_orgs.nunique()
    print(f"  schools_org_all: org rows={len(dup_orgs):,} unique nu_guid={dup_orgs.nunique():,} "
          f"DUP org rows={dups:,} (was 2,072 before the fix)")

    return enriched, all_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--schools", default="schools_combined_enriched_ceeb.csv")
    parser.add_argument("--org", default="nu_master_org_data.csv")
    parser.add_argument("--outdir", default=".")
    args = parser.parse_args()

    enriched, all_df = rebuild(args.schools, args.org)

    enriched_path = os.path.join(args.outdir, "schools_org_enriched.csv")
    all_path = os.path.join(args.outdir, "schools_org_all.csv")
    enriched.to_csv(enriched_path, index=False)
    all_df.to_csv(all_path, index=False)
    print(f"\nWrote {enriched_path} ({enriched.shape[0]:,} x {enriched.shape[1]})")
    print(f"Wrote {all_path} ({all_df.shape[0]:,} x {all_df.shape[1]})")
