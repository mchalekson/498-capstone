"""
Build CEEB crosswalks for the three sources that carry no NCES/NCESSCH ID of
their own — IB, ISBE, and the CPS Opportunity Index — against the
CEEB-anchored "NU master" school list (see data/NU-Master/README.md).

Today (see combine_schools.py) these three are fuzzy-matched directly against
NCES tables, independently of each other. Once a current NU master exists,
matching each source to CEEB once means they're all transitively joinable
through a single shared ID instead of three separate ad hoc name-matches.

No-op if the master file isn't present (NU_MASTER_PATH in config.py) — safe
to leave wired into run_all.py permanently. It starts producing tables the
moment a current file is dropped in place; nothing else needs to change.

Produces tables: ib_ceeb_crosswalk, isbe_ceeb_crosswalk, cps_ceeb_crosswalk
"""

import os
import pandas as pd
from sqlalchemy import create_engine, text
from config import DATABASE_URL, NU_MASTER_PATH
import db_utils
from crosswalk_matcher import match_to_master
from combine_schools import STATE_ABBR_TO_NAME

STATE_NAME_TO_ABBR = {v: k for k, v in STATE_ABBR_TO_NAME.items()}


def _to_abbr(series: pd.Series) -> pd.Series:
    """Canonicalize a state column to 2-letter abbreviation, whichever
    convention it arrives in — the NU master's actual format is unknown
    until a current copy exists, so don't assume."""
    s = series.astype(str).str.strip().str.upper()
    full_name_rows = s.str.len() > 2
    s = s.where(~full_name_rows, s.map(STATE_NAME_TO_ABBR))
    return s


def _load_master():
    if not os.path.exists(NU_MASTER_PATH):
        print(f"  NU master not found at {NU_MASTER_PATH} — skipping CEEB crosswalk.")
        print("  This is expected until a current file is provided (Bob's copy is "
              "stale); see data/NU-Master/README.md for what's needed.")
        return None
    master = pd.read_excel(NU_MASTER_PATH) if NU_MASTER_PATH.endswith((".xlsx", ".xls")) \
        else pd.read_csv(NU_MASTER_PATH)
    master["Region"] = _to_abbr(master["Region"])
    return master


def _write(engine, df: pd.DataFrame, table_name: str):
    df.to_sql(table_name, engine, if_exists="replace", index=False,
              method=db_utils.psql_insert_copy)
    accepted = (df["tier"] == "auto_accept").sum()
    print(f"  {len(df):,} rows → {table_name} ({accepted} auto-accepted) ✓")
    with engine.connect() as conn:
        conn.execute(text(f'ALTER TABLE {table_name} ADD PRIMARY KEY (source_id)'))
        conn.commit()


def build_all(engine):
    master = _load_master()
    if master is None:
        return

    # IB — no state/city field in the source at all, so this is a nationwide,
    # unblocked match. Never trust an auto_accept here (see combine_schools.py's
    # note on common names like "Mercy High School" colliding across states).
    ib = pd.read_sql("SELECT school_id, name FROM ib_schools", engine)
    ib_cw = match_to_master(ib, master, src_name="name", src_id="school_id")
    ib_cw["tier"] = ib_cw["tier"].replace("auto_accept", "review")
    _write(engine, ib_cw, "ib_ceeb_crosswalk")

    # ISBE — Illinois only, has a city field to block/bonus on.
    isbe = pd.read_sql(
        "SELECT rcdts, school_name, city FROM isbe_general WHERE school_name IS NOT NULL",
        engine,
    )
    isbe["state"] = "IL"
    isbe_cw = match_to_master(isbe, master, src_name="school_name", src_id="rcdts",
                               src_state="state", src_city="city")
    _write(engine, isbe_cw, "isbe_ceeb_crosswalk")

    # CPS Opportunity Index — Chicago/Illinois only, no city field of its own.
    cps = pd.read_sql("SELECT school_id, school_name FROM cps_opportunity_index", engine)
    cps["state"] = "IL"
    cps_cw = match_to_master(cps, master, src_name="school_name", src_id="school_id",
                              src_state="state")
    _write(engine, cps_cw, "cps_ceeb_crosswalk")


if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    build_all(engine)
