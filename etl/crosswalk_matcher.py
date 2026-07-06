"""
crosswalk_matcher.py — reusable CEEB<->NCES (or any source) fuzzy matcher.

Matches a SOURCE table (name + state [+ city]) against the NU master (which carries
CEEB), using state blocking and a two-signal score (token_set for recall,
token_sort as a precision guard against subset/generic-token inflation).

Usage:
    from crosswalk_matcher import match_to_master, normalize_name
    cw = match_to_master(source_df, master_df,
                         src_name='PSS_INST', src_state='PSS_STABB', src_city='PSS_CITY',
                         src_id='PSS_SCHOOL_ID')

Dependencies: pandas, rapidfuzz
"""
import re
import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process


def normalize_name(s: str) -> str:
    """Light, non-destructive name normalization."""
    if pd.isna(s):
        return ""
    s = str(s).upper()
    s = re.sub(r"\bSAINT\b", "ST", s)
    s = re.sub(r"\bMOUNT\b", "MT", s)
    s = re.sub(r"&", " AND ", s)
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # "H S" / "HS" -> "HIGH SCHOOL": common NCES abbreviation that otherwise
    # drops real matches below threshold (e.g. "New Trier Township H S"
    # scored a 75 against "New Trier Township High School" pre-fix).
    s = re.sub(r"\bH S\b", "HIGH SCHOOL", s)
    s = re.sub(r"\bHS\b", "HIGH SCHOOL", s)
    return s


def _tier(row, accept=(90, 85), accept_city=(88, 80), review=(80, 65)):
    if pd.isna(row["CEEB"]):
        return "no_candidate"
    tset, tsort, city = row["name_score_set"], row["name_score_sort"], row["city_match"]
    if (tset >= accept[0] and tsort >= accept[1]) or (
        city and tset >= accept_city[0] and tsort >= accept_city[1]
    ):
        return "auto_accept"
    if tset >= review[0] and tsort >= review[1]:
        return "review"
    return "reject"


def match_to_master(
    source_df, master_df,
    src_name, src_id, src_state=None, src_city=None,
    master_name="Name", master_state="Region", master_city="City", master_ceeb="CEEB",
):
    """Return a crosswalk DataFrame linking each source row to its best NU-master CEEB.

    master_df should already be filtered to the relevant scope (e.g. High School,
    matching school type). Blocking is on exact state when src_state is given.

    src_state=None matches every source row against the entire master with no
    blocking (e.g. IB, which carries no state/city field at all) — expect a
    much higher false-positive rate; treat every result as "review", never
    auto-accept.
    """
    m = master_df.copy()
    m["_nm"] = m[master_name].map(normalize_name)
    m["_city"] = m[master_city].astype(str).str.upper().str.strip() if master_city in m else ""
    s = source_df.copy()
    s["_nm"] = s[src_name].map(normalize_name)
    s["_city"] = s[src_city].astype(str).str.upper().str.strip() if src_city else ""

    groups = s.groupby(src_state) if src_state else [(None, s)]

    rows = []
    for st, grp in groups:
        cand = m if st is None else m[m[master_state] == st]
        if cand.empty:
            for _, r in grp.iterrows():
                rows.append([r[src_id], r[src_name], st, r["_city"], None, None, None,
                             np.nan, np.nan, False])
            continue
        names, idx = cand["_nm"].tolist(), cand.index.tolist()
        for _, r in grp.iterrows():
            best = process.extractOne(r["_nm"], names, scorer=fuzz.token_set_ratio)
            _, tset, pos = best
            c = cand.loc[idx[pos]]
            tsort = fuzz.token_sort_ratio(r["_nm"], c["_nm"])
            city_match = bool(r["_city"]) and r["_city"] not in ("", "NAN") and r["_city"] == c["_city"]
            rows.append([r[src_id], r[src_name], st, r["_city"], c[master_ceeb],
                         c[master_name], c["_city"], tset, tsort, city_match])

    cw = pd.DataFrame(rows, columns=[
        "source_id", "source_name", "state", "source_city",
        "CEEB", "nu_name", "nu_city", "name_score_set", "name_score_sort", "city_match"])
    cw["tier"] = cw.apply(_tier, axis=1)
    cw["needs_review"] = cw["tier"] == "review"
    return cw


if __name__ == "__main__":
    import sys
    print("Import and call match_to_master(...). See module docstring for usage.")
