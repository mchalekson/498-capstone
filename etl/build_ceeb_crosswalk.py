"""
Build the NCES<->CEEB junction, plus CEEB crosswalks for the three sources
that carry no NCES/NCESSCH ID of their own (IB, ISBE, CPS).

build_nces_junction() is the core deliverable: matches our own NCES public
(HS-filtered) and private tables against the UC Boulder NCES<->CEEB
crosswalk (see data/CEEB-Crosswalk/README.md) by name+state(+city), since
our own ncessch is only the truncated 7-digit ELSI export id and can't be
directly ID-joined against that crosswalk's 12-digit ids yet. Runs
unconditionally — the crosswalk file is a real, already-loaded source, not
a placeholder.

build_all() matches IB/ISBE/CPS against a second, still-hypothetical
CEEB-anchored "NU master" school list (see data/NU-Master/README.md) —
today (see combine_schools.py) these three are fuzzy-matched directly
against NCES tables, independently of each other. No-op if that file isn't
present (NU_MASTER_PATH in config.py) — safe to leave wired into
run_all.py permanently.

Produces tables: nces_public_ceeb_crosswalk, nces_private_ceeb_crosswalk,
ib_ceeb_crosswalk, isbe_ceeb_crosswalk, cps_ceeb_crosswalk
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


def _load_nces_ceeb_source(engine):
    m = pd.read_sql("SELECT hs_name, hs_state, hs_city, hs_ceeb FROM nces_ceeb_crosswalk_source", engine)
    m["hs_state"] = _to_abbr(m["hs_state"])
    return m


def build_nces_junction(engine):
    print("Building NCES<->CEEB junction (UC Boulder crosswalk, name+state match)...")
    master = _load_nces_ceeb_source(engine)

    # Uses nces_public_schools_clean filtered to High/Secondary, not the
    # separately-pulled nces_public_hs_grades_9_12 extract — spot-checking
    # against the New Trier example (NCES 172820002975 / CEEB 144430) found
    # that extract missing New Trier entirely (it's coded "Secondary", and
    # split across two campus rows -- Winnetka/Northfield -- for one CEEB
    # code), while this broader table has it.
    public = pd.read_sql(
        "SELECT ncessch, school_name_2024_25 AS name, location_city_2024_25 AS city, "
        "state_name_2024_25 AS state FROM nces_public_schools_clean "
        "WHERE school_level_2024_25 IN ('High', 'Secondary')", engine,
    )
    public["state"] = public["state"].str.strip().str.upper().map(STATE_NAME_TO_ABBR)
    public_cw = match_to_master(public, master, src_name="name", src_id="ncessch",
                                 src_state="state", src_city="city",
                                 master_name="hs_name", master_state="hs_state",
                                 master_city="hs_city", master_ceeb="hs_ceeb")
    accepted = (public_cw["tier"] == "auto_accept").sum()
    print(f"  Public HS <-> CEEB: {accepted}/{len(public_cw)} auto-accepted")
    _write(engine, public_cw, "nces_public_ceeb_crosswalk")

    private = pd.read_sql(
        "SELECT pss_school_id, pss_inst AS name, pss_city AS city, pss_stabb AS state "
        "FROM nces_private_merged_clean", engine,
    )
    private["state"] = _to_abbr(private["state"])
    private_cw = match_to_master(private, master, src_name="name", src_id="pss_school_id",
                                  src_state="state", src_city="city",
                                  master_name="hs_name", master_state="hs_state",
                                  master_city="hs_city", master_ceeb="hs_ceeb")
    accepted = (private_cw["tier"] == "auto_accept").sum()
    print(f"  Private HS <-> CEEB: {accepted}/{len(private_cw)} auto-accepted")
    _write(engine, private_cw, "nces_private_ceeb_crosswalk")


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
