"""
Load the NU master school list (Bob's College-Board-style org export) into
PostgreSQL — see data/NU-Master/README.md for what this file is and why it
matters (the CEEB-anchored master list build_ceeb_crosswalk.py needs).

Table created:
  nu_master_org_data — one row per org (PK: guid). CEEB is the shared join
  key against schools_combined_enriched_ceeb (see load_schools_ceeb.py) and
  against NCES/IB/ISBE/CPS via build_ceeb_crosswalk.py.
"""

import re
import pandas as pd
from sqlalchemy import create_engine, text
from config import DATABASE_URL, NU_MASTER_PATH
import db_utils

# Pure section-divider columns in the source export — same literal string
# repeated on every row, no information content.
DIVIDER_COLUMNS = ["----", "--Org Details--", "--Org Details--School Profile Info--"]


def _normalize_col(c: str) -> str:
    c = c.strip().replace("%", "pct").replace("#", "num")
    c = re.sub(r"[^A-Za-z0-9]+", "_", c)
    return re.sub(r"_+", "_", c).strip("_").lower()


def flag_ceeb_arithmetic_twin(df):
    """
    Marks CEEB codes that have an "arithmetic twin" elsewhere in the file: a code of the
    form "abcde0" (six digits, ends in 0, does not start with 0) whose mirror "0abcde"
    (same five core digits, zero moved to the front) is also present, e.g. "525040" and
    "052504". This began as a suspected data-quality flag ("ceeb_suspected_padding_shift")
    on the theory that such pairs were the signature of a 6-digit zero-padded CEEB stored
    as a number upstream (losing the leading zero) and re-padded on the wrong side.

    That theory was WRONG -- the flag is retained only as a benign, descriptive diagnostic.
    Adam (client-side) manually checked the flagged codes against the College Board SAT
    school-code search and an ACT 6-digit high-school code master list (2026-08-10), and we
    re-ran the full flagged list against that same ACT list: of the 644 flagged codes, 643
    are valid ACT codes that match the real school by name, and 641 of the "mirror" codes
    are themselves real, DIFFERENT schools. So essentially every flagged "pair" is just two
    legitimate schools whose codes happen to be arithmetic mirror images -- an artifact of
    how densely the 6-digit high-school code space is populated, NOT corruption. The CEEB
    column is read straight from the source .xlsx as text and is correct.

    Where the numeric-storage damage DID land is the custom_id column, not CEEB: 73 of the
    84 duplicate custom_id values pair two schools whose CEEBs collapse to the same integer
    once you drop leading zeros and a trailing digit (int(a) == int(b) // 10). That only
    confirms custom_id is not a usable key (already known: 0% federal-ID match, non-unique);
    it says nothing about the CEEBs. This column is informational and is not consumed
    anywhere downstream (no join, crosswalk, or model reads it).
    """
    ceeb = df["ceeb"].astype(str).str.zfill(6)
    valid_ceebs = set(ceeb[df["ceeb"].notna()])
    mirror_candidate = "0" + ceeb.str[:-1]
    has_twin = (
        df["ceeb"].notna()
        & (ceeb.str[-1] == "0")
        & (ceeb.str[0] != "0")
        & mirror_candidate.isin(valid_ceebs)
    )
    df["ceeb_has_arithmetic_twin"] = has_twin
    print(f"  [ceeb check] {has_twin.sum():,} rows have an arithmetic-twin CEEB elsewhere in "
          f"the file (benign coincidence, validated against ACT/College Board -- NOT corruption; "
          f"see flag_ceeb_arithmetic_twin docstring). Informational only, unused downstream.")
    return df


def load_nu_master(engine):
    print(f"Reading NU master org data from {NU_MASTER_PATH}...")
    # CEEB/GUID as text — numeric inference would drop CEEB's leading zeros
    # (e.g. "010370" -> 10370), breaking the exact-match join in combine_schools.py.
    df = pd.read_excel(NU_MASTER_PATH, sheet_name="Export", dtype={"CEEB": str, "GUID": str})
    df = df.drop(columns=[c for c in DIVIDER_COLUMNS if c in df.columns])
    df.columns = [_normalize_col(c) for c in df.columns]
    df = flag_ceeb_arithmetic_twin(df)

    print(f"  {len(df):,} rows, {len(df.columns)} columns")
    df.to_sql("nu_master_org_data", engine, if_exists="replace", index=False,
              method=db_utils.psql_insert_copy)
    print("  Loaded nu_master_org_data ✓")

    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE nu_master_org_data ADD PRIMARY KEY (guid)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_nu_master_org_data_ceeb ON nu_master_org_data (ceeb)"))
        conn.commit()


if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    load_nu_master(engine)
