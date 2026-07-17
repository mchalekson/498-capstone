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


def flag_ceeb_padding_shift(df):
    """
    Investigated the "custom_id" column's 84 duplicate values (raised in the 2026-07-14
    meeting: "custom ID variable from Org Data -- probably some custom thing in system").
    custom_id doesn't match any federal ID we have (0% match against NCES's 7-digit school
    ID) and isn't fully unique, so it's not usable as a join key -- but 62 of those 84
    duplicate pairs turned out to share a specific, mechanical relationship between the two
    rows' CEEB codes: one is the exact left-shift of the other (e.g. "050003" / "500030" --
    strip a leading zero, append a trailing zero), the classic signature of a 6-digit
    zero-padded code getting stored as a number somewhere upstream (losing the leading
    zero) and then re-padded on the wrong side. Across the full file, 644 CEEB codes ending
    in "0" have a leading-zero counterpart also present elsewhere in the file -- some
    fraction of these are certainly real, unrelated CEEBs that coincidentally fit the
    pattern, but the 62 pairs confirmed via the independent custom_id collision make clear
    this is a real upstream data issue in Bob's export, not our own ETL (CEEB is read
    directly from the source .xlsx as text, unmodified, above).

    This flags suspects for downstream caution -- it does NOT attempt to guess which of a
    pair (if either) is correct, since that would risk silently "fixing" a code with no real
    evidence for which value is right.
    """
    ceeb = df["ceeb"].astype(str).str.zfill(6)
    valid_ceebs = set(ceeb[df["ceeb"].notna()])
    shifted_candidate = "0" + ceeb.str[:-1]
    suspect = (
        df["ceeb"].notna()
        & (ceeb.str[-1] == "0")
        & (ceeb.str[0] != "0")
        & shifted_candidate.isin(valid_ceebs)
    )
    df["ceeb_suspected_padding_shift"] = suspect
    print(f"  [ceeb check] {suspect.sum():,} rows flagged with a suspected leading-zero/"
          f"trailing-zero CEEB shift (see flag_ceeb_padding_shift docstring) -- not corrected, "
          f"just flagged for caution downstream")
    return df


def load_nu_master(engine):
    print(f"Reading NU master org data from {NU_MASTER_PATH}...")
    # CEEB/GUID as text — numeric inference would drop CEEB's leading zeros
    # (e.g. "010370" -> 10370), breaking the exact-match join in combine_schools.py.
    df = pd.read_excel(NU_MASTER_PATH, sheet_name="Export", dtype={"CEEB": str, "GUID": str})
    df = df.drop(columns=[c for c in DIVIDER_COLUMNS if c in df.columns])
    df.columns = [_normalize_col(c) for c in df.columns]
    df = flag_ceeb_padding_shift(df)

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
