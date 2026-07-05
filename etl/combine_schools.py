"""
Combine all loaded datasets into analysis-ready, grain-appropriate tables.

Per the merge strategy in EDA_NCES_private_EN.md:
  - Public/private schools are the school-level backbone.
  - IB, ISBE, and CPS have no shared ID with NCES, so they're linked by
    fuzzy name (+ city/state where available) matching via rapidfuzz.
  - College Board AP and NAEP are state-level aggregates; they're attached
    as repeated context columns (same value for every school in a state),
    not fanned out into a separate row per school.
  - Census school finance and SAIPE poverty are district-level, but there
    is no reliable school/private-school -> district crosswalk in the data
    as provided (see clean_nces/views.sql notes), so they're aggregated to
    state level here too, same as illinois_schools_enriched.

Produces tables: public_schools_enriched, private_schools_enriched,
                 cps_nces_crosswalk
"""

import re
import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process
from sqlalchemy import create_engine, text
from config import DATABASE_URL
import db_utils

STATE_ABBR_TO_NAME = {
    "AL": "ALABAMA", "AK": "ALASKA", "AZ": "ARIZONA", "AR": "ARKANSAS",
    "CA": "CALIFORNIA", "CO": "COLORADO", "CT": "CONNECTICUT", "DE": "DELAWARE",
    "DC": "DISTRICT OF COLUMBIA", "FL": "FLORIDA", "GA": "GEORGIA", "HI": "HAWAII",
    "ID": "IDAHO", "IL": "ILLINOIS", "IN": "INDIANA", "IA": "IOWA", "KS": "KANSAS",
    "KY": "KENTUCKY", "LA": "LOUISIANA", "ME": "MAINE", "MD": "MARYLAND",
    "MA": "MASSACHUSETTS", "MI": "MICHIGAN", "MN": "MINNESOTA", "MS": "MISSISSIPPI",
    "MO": "MISSOURI", "MT": "MONTANA", "NE": "NEBRASKA", "NV": "NEVADA",
    "NH": "NEW HAMPSHIRE", "NJ": "NEW JERSEY", "NM": "NEW MEXICO", "NY": "NEW YORK",
    "NC": "NORTH CAROLINA", "ND": "NORTH DAKOTA", "OH": "OHIO", "OK": "OKLAHOMA",
    "OR": "OREGON", "PA": "PENNSYLVANIA", "RI": "RHODE ISLAND", "SC": "SOUTH CAROLINA",
    "SD": "SOUTH DAKOTA", "TN": "TENNESSEE", "TX": "TEXAS", "UT": "UTAH",
    "VT": "VERMONT", "VA": "VIRGINIA", "WA": "WASHINGTON", "WV": "WEST VIRGINIA",
    "WI": "WISCONSIN", "WY": "WYOMING", "PR": "PUERTO RICO",
}


def normalize_name(s) -> str:
    """Light, non-destructive name normalization for fuzzy matching."""
    if pd.isna(s):
        return ""
    s = str(s).upper()
    s = re.sub(r"\bSAINT\b", "ST", s)
    s = re.sub(r"\bMOUNT\b", "MT", s)
    s = re.sub(r"&", " AND ", s)
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def fuzzy_match(source_df, master_df, src_name, master_name,
                 src_block=None, master_block=None, master_id="id",
                 accept=(90, 85), review=(80, 65)):
    """
    Match each row in source_df to its best name match in master_df.
    If *_block columns are given, candidates are restricted to matching
    block values first (e.g. state) to cut down on false positives.

    Uses two signals, same approach as crosswalk_matcher.py: token_set_ratio
    picks the best candidate (good recall, but inflated by shared generic
    words like "Catholic"/"Memorial"/"High School"), then token_sort_ratio
    on that specific pair acts as a precision guard — a real match needs
    both, not just one loosely-overlapping token_set score. Without this
    second signal, one-off nationwide matches (no state to block on, e.g.
    IB) produce clear false positives (e.g. "Kent School" <-> "Kent-Meridian
    High School" scoring 100 on token_set_ratio alone).

    Returns a DataFrame with one row per source_df row: best match id,
    both scores, and a confidence tier (auto_accept / review / reject /
    no_candidate).
    """
    s = source_df.copy()
    s["_nm"] = s[src_name].map(normalize_name)
    m = master_df.copy()
    m["_nm"] = m[master_name].map(normalize_name)

    results = []
    if src_block and master_block:
        groups = s.groupby(src_block)
    else:
        groups = [(None, s)]

    for key, grp in groups:
        cand = m[m[master_block] == key] if (src_block and master_block) else m
        if cand.empty:
            for idx in grp.index:
                results.append((idx, None, 0, 0, "no_candidate"))
            continue
        names = cand["_nm"].tolist()
        for idx, row in grp.iterrows():
            best = process.extractOne(row["_nm"], names, scorer=fuzz.token_set_ratio)
            if best is None:
                results.append((idx, None, 0, 0, "no_candidate"))
                continue
            _, tset, pos = best
            match_row = cand.iloc[pos]
            tsort = fuzz.token_sort_ratio(row["_nm"], match_row["_nm"])
            if tset >= accept[0] and tsort >= accept[1]:
                tier = "auto_accept"
            elif tset >= review[0] and tsort >= review[1]:
                tier = "review"
            else:
                tier = "reject"
            results.append((idx, match_row[master_id], tset, tsort, tier))

    out = pd.DataFrame(results, columns=["_src_idx", "match_id", "match_score_set", "match_score_sort", "match_tier"])
    out = out.set_index("_src_idx")
    return out


def _state_ap_context(engine):
    """Most recent state-level AP participation + availability, wide format."""
    part = pd.read_sql(
        "SELECT state, value AS ap_pct_participation FROM ap_participation "
        "WHERE subgroup = 'All' AND metric = 'pct_participation' AND year = '2025'",
        engine,
    )
    avail = pd.read_sql(
        "SELECT state, value AS ap_pct_offers_5plus_courses FROM ap_availability "
        "WHERE subgroup = 'All' AND threshold = 'At least five AP courses' "
        "AND metric = 'Percentage of public high schools that offers' AND year = 2024",
        engine,
    )
    part["ap_pct_participation"] = pd.to_numeric(part["ap_pct_participation"], errors="coerce")
    avail["ap_pct_offers_5plus_courses"] = pd.to_numeric(avail["ap_pct_offers_5plus_courses"], errors="coerce")
    ctx = part.merge(avail, on="state", how="outer")
    ctx["state_upper"] = ctx["state"].str.upper()
    ctx = ctx.drop(columns=["state"])
    # A parsing quirk in the source spreadsheet duplicates one state's row
    # (Iowa); state context tables must be one row per state by construction.
    dupes = ctx["state_upper"].duplicated().sum()
    if dupes:
        print(f"  Note: {dupes} duplicate state row(s) in AP context, averaging")
        ctx = ctx.groupby("state_upper", as_index=False).mean(numeric_only=True)
    return ctx


def _state_naep_context(engine):
    """Most recent (2024) grade-8 NAEP scores, wide format."""
    naep = pd.read_sql(
        "SELECT state, subject, avg_scale_score FROM naep_assessments_clean "
        "WHERE grade = 8 AND year = 2024",
        engine,
    )
    wide = naep.pivot_table(index="state", columns="subject", values="avg_scale_score", aggfunc="first")
    wide.columns = [f"naep_grade8_{c}" for c in wide.columns]
    wide = wide.reset_index()
    wide["state_upper"] = wide["state"].str.upper()
    return wide.drop(columns=["state"])


def _state_finance_poverty_context(engine):
    """State-aggregated Census finance + SAIPE poverty (see module docstring)."""
    saipe = pd.read_sql(
        "SELECT fips_state, SUM(child_poverty_estimate) AS state_child_poverty_est, "
        "SUM(child_population_5_17) AS state_child_pop FROM census_saipe_poverty_clean "
        "GROUP BY fips_state",
        engine,
    )
    finance = pd.read_sql(
        "SELECT fips_state, SUM(total_revenue_000s) AS state_total_revenue_000s, "
        "SUM(federal_revenue_000s) AS state_federal_revenue_000s FROM census_school_finances_clean "
        "GROUP BY fips_state",
        engine,
    )
    return saipe.merge(finance, on="fips_state", how="outer")


def build_public_schools_enriched(engine):
    print("Combining public_schools_enriched (nationwide)...")
    n = pd.read_sql("SELECT * FROM nces_public_schools_clean", engine)
    n["state_upper"] = n["state_name_2024_25"].str.upper()

    isbe = pd.read_sql(
        "SELECT rcdts, school_name, city, summative_designation, title_i_status, "
        "count_student_enrollment FROM isbe_general", engine,
    )
    isbe["_name_key"] = isbe["school_name"].map(normalize_name)
    isbe["_city_key"] = isbe["city"].astype(str).str.upper().str.strip()
    isbe = isbe.drop_duplicates(subset=["_name_key", "_city_key"], keep="first")

    n["_name_key"] = n["school_name_2024_25"].map(normalize_name)
    n["_city_key"] = n["location_city_2024_25"].astype(str).str.upper().str.strip()

    # ISBE only covers Illinois; joining it against the full nationwide table
    # (without restricting to IL) causes false cross-state matches wherever a
    # generic school name + city happens to repeat in another state.
    is_il = n["location_state_abbr_2024_25"].str.strip() == "IL"
    n_il = n[is_il].merge(isbe, on=["_name_key", "_city_key"], how="left", suffixes=("", "_isbe"))
    n_other = n[~is_il]
    df = pd.concat([n_il, n_other], ignore_index=True)
    df = df.drop(columns=["_name_key", "_city_key"])

    ap_ctx = _state_ap_context(engine)
    naep_ctx = _state_naep_context(engine)
    fin_ctx = _state_finance_poverty_context(engine)
    fin_ctx["state_upper"] = fin_ctx["fips_state"].astype(str)  # joined below via ansi code instead

    df = df.merge(ap_ctx, on="state_upper", how="left")
    df = df.merge(naep_ctx, on="state_upper", how="left")
    df = df.merge(
        fin_ctx.drop(columns=["state_upper"]),
        left_on="ansi_fips_state_code_latest_available_year",
        right_on="fips_state",
        how="left",
    )

    df.to_sql("public_schools_enriched", engine, if_exists="replace", index=False,
              method=db_utils.psql_insert_copy)
    print(f"  {len(df):,} rows → public_schools_enriched ✓")

    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE public_schools_enriched ADD PRIMARY KEY (ncessch)"))
        conn.commit()


def build_private_schools_enriched(engine):
    print("Combining private_schools_enriched (nationwide)...")
    p = pd.read_sql("SELECT * FROM nces_private_merged_clean", engine)
    p["state_upper"] = p["pss_stabb"].map(STATE_ABBR_TO_NAME)

    # Direct join to ELSI private schools — same NCES ID system (per EDA: ~72% match)
    elsi = pd.read_sql("SELECT * FROM nces_private_schools_clean", engine)
    elsi = elsi.add_prefix("elsi_")
    df = p.merge(elsi, left_on="pss_school_id", right_on="elsi_ncessch", how="left")
    matched = df["elsi_ncessch"].notna().sum()
    print(f"  ELSI direct-ID join: {matched}/{len(df)} matched")

    # IB flag — fuzzy name match, nationwide (IB data has no state/city field to
    # block on). This is not safe to auto-accept: e.g. 4 different "Mercy High
    # School"s in 4 different states all scored a perfect 100/100 match against
    # the same single IB record, since common institutional names legitimately
    # repeat nationwide and there's no state to disambiguate them. Every match
    # is capped at "review" regardless of score — a human still needs to confirm.
    ib = pd.read_sql("SELECT school_id AS ib_school_id, name AS ib_name, offers_any_ib FROM ib_schools", engine)
    ib_match = fuzzy_match(df, ib, src_name="pss_inst", master_name="ib_name", master_id="ib_school_id")
    df["ib_school_id"] = ib_match["match_id"]
    df["ib_match_score_set"] = ib_match["match_score_set"]
    df["ib_match_score_sort"] = ib_match["match_score_sort"]
    df["ib_match_tier"] = ib_match["match_tier"].replace("auto_accept", "review")
    reviewable = (df["ib_match_tier"] == "review").sum()
    print(f"  IB fuzzy match: {reviewable}/{len(df)} candidates flagged for review (nationwide, no state blocking — none auto-accepted)")

    # ISBE — Illinois private schools only, name + city blocking
    isbe = pd.read_sql(
        "SELECT rcdts, school_name, city FROM isbe_general WHERE school_name IS NOT NULL", engine,
    )
    isbe["_state_block"] = "IL"
    df["_state_block"] = df["pss_stabb"]
    isbe_match = fuzzy_match(
        df, isbe, src_name="pss_inst", master_name="school_name",
        src_block="_state_block", master_block="_state_block", master_id="rcdts",
    )
    df["isbe_rcdts"] = isbe_match["match_id"]
    df["isbe_match_score_set"] = isbe_match["match_score_set"]
    df["isbe_match_score_sort"] = isbe_match["match_score_sort"]
    df["isbe_match_tier"] = isbe_match["match_tier"]
    df = df.drop(columns=["_state_block"])
    il_count = (df["pss_stabb"] == "IL").sum()
    il_accepted = ((df["pss_stabb"] == "IL") & (df["isbe_match_tier"] == "auto_accept")).sum()
    print(f"  ISBE fuzzy match (IL only): {il_accepted}/{il_count} IL private schools auto-accepted")

    # State-level AP / NAEP / finance+poverty context
    ap_ctx = _state_ap_context(engine)
    naep_ctx = _state_naep_context(engine)
    fin_ctx = _state_finance_poverty_context(engine)

    df = df.merge(ap_ctx, on="state_upper", how="left")
    df = df.merge(naep_ctx, on="state_upper", how="left")
    df = df.merge(fin_ctx, left_on="pss_fips", right_on="fips_state", how="left")

    df.to_sql("private_schools_enriched", engine, if_exists="replace", index=False,
              method=db_utils.psql_insert_copy)
    print(f"  {len(df):,} rows → private_schools_enriched ✓")

    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE private_schools_enriched ADD PRIMARY KEY (pss_school_id)"))
        conn.commit()


def build_cps_nces_crosswalk(engine):
    """CPS Opportunity Index schools have no NCES ID; fuzzy-match by name to
    both NCES public schools and ISBE, blocking on Chicago city/IL state."""
    print("Combining cps_nces_crosswalk...")
    cps = pd.read_sql("SELECT school_id AS cps_school_id, school_name AS cps_school_name FROM cps_opportunity_index", engine)
    cps["_block"] = "CHICAGO"

    nces = pd.read_sql(
        "SELECT ncessch, school_name_2024_25 AS school_name FROM nces_public_schools_clean "
        "WHERE location_city_2024_25 ILIKE 'chicago' AND TRIM(location_state_abbr_2024_25) = 'IL'",
        engine,
    )
    nces["_block"] = "CHICAGO"
    nces_match = fuzzy_match(cps, nces, src_name="cps_school_name", master_name="school_name",
                              src_block="_block", master_block="_block", master_id="ncessch")

    isbe = pd.read_sql(
        "SELECT rcdts, school_name FROM isbe_general WHERE city ILIKE 'chicago' AND school_name IS NOT NULL", engine,
    )
    isbe["_block"] = "CHICAGO"
    isbe_match = fuzzy_match(cps, isbe, src_name="cps_school_name", master_name="school_name",
                              src_block="_block", master_block="_block", master_id="rcdts")

    cps["ncessch"] = nces_match["match_id"]
    cps["nces_match_score_set"] = nces_match["match_score_set"]
    cps["nces_match_score_sort"] = nces_match["match_score_sort"]
    cps["nces_match_tier"] = nces_match["match_tier"]
    cps["rcdts"] = isbe_match["match_id"]
    cps["isbe_match_score_set"] = isbe_match["match_score_set"]
    cps["isbe_match_score_sort"] = isbe_match["match_score_sort"]
    cps["isbe_match_tier"] = isbe_match["match_tier"]
    cps = cps.drop(columns=["_block"])

    nces_accepted = (cps["nces_match_tier"] == "auto_accept").sum()
    isbe_accepted = (cps["isbe_match_tier"] == "auto_accept").sum()
    print(f"  NCES match: {nces_accepted}/{len(cps)} auto-accepted; ISBE match: {isbe_accepted}/{len(cps)} auto-accepted")

    cps.to_sql("cps_nces_crosswalk", engine, if_exists="replace", index=False,
               method=db_utils.psql_insert_copy)
    print(f"  {len(cps):,} rows → cps_nces_crosswalk ✓")

    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE cps_nces_crosswalk ADD PRIMARY KEY (cps_school_id)"))
        conn.commit()


if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    build_public_schools_enriched(engine)
    build_private_schools_enriched(engine)
    build_cps_nces_crosswalk(engine)
