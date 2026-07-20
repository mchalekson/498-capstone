"""
LLM adjudication of fuzzy-match candidate pairs (CEEB crosswalks, IB, etc.).

Three-stage funnel (see docs/LLM_ADJUDICATION.md):
  1. Deterministic rules resolve the safe cases (same-city name-superset accept;
     different-city weak-name reject; symmetric-distinctive-token accept).
  2. The remainder goes to an LLM as batched yes/no/unsure judgments.
  3. 'unsure' rows stay tier=review for human spot-check.

The 2026-07 run was adjudicated in-session by Claude (decision_source
'llm_claude_fable_5' in *_adjudicated.csv). This script reproduces that flow
against the Anthropic API for future refreshes:

  export ANTHROPIC_API_KEY=...
  python llm_adjudicate_matches.py csv_exports/nces_public_ceeb_crosswalk.csv

Writes <input>_adjudicated.csv with final_tier / decision_source / CEEB_final.
"""

import json
import os
import re
import sys

import numpy as np
import pandas as pd

MODEL = os.getenv("ADJUDICATION_MODEL", "claude-sonnet-5")
BATCH = 40

GENERIC = set(
    """HIGH SCHOOL SCH SCHOOLS HS SHS JSHS JR SR JUNIOR SENIOR MIDDLE AREA COMM COMMUNITY
    TOWNSHIP TWNSHP TWP TOWN CITY COUNTY CO REGIONAL REGL UPPER COMBINED CONSOLIDATED CONS
    THE OF AND FOR AT ON IN HI PUBLIC CAMPUS GRADE DISTRICT DIST""".split()
)
ABBREV = {"FT": "FORT", "MT": "MOUNT", "ST": "SAINT", "CTR": "CENTER", "TECH": "TECHNOLOGY",
          "PREP": "PREPARATORY", "ACAD": "ACADEMY", "MEM": "MEMORIAL"}

PROMPT = """You are adjudicating school-matching candidates for an admissions database.
Each line: ID | our school, city, state <> candidate school, candidate city.
Answer for each ID whether they are the SAME school (name variants, renamings,
abbreviations, campus of same institution) or DIFFERENT schools (e.g. an
alternative/virtual/continuation program matched to the regular high school,
or same-name schools in different towns). Be conservative: attaching a wrong
CEEB code is worse than leaving one blank.
Return strict JSON: {"decisions": [{"id": "...", "verdict": "same|different|unsure"}]}.

Pairs:
"""


def toks(name):
    t = re.findall(r"[A-Z]+", str(name).upper())
    return [ABBREV.get(x, x) for x in t if x not in GENERIC and not x.isdigit()]


def sym_match(a, b):
    A, B = toks(a), toks(b)
    if not A or not B:
        return False
    cover = lambda X, Y: all(any(x == y or x.startswith(y) or y.startswith(x) for y in Y) for x in X)
    return cover(A, B) and cover(B, A)


def call_llm(lines):
    import anthropic

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=MODEL, max_tokens=4000,
        messages=[{"role": "user", "content": PROMPT + "\n".join(lines)}],
    )
    text = msg.content[0].text
    return json.loads(text[text.index("{"): text.rindex("}") + 1])["decisions"]


def main(path):
    d = pd.read_csv(path, dtype=str)
    d["set_"] = d["name_score_set"].astype(float)
    d["sort_"] = d["name_score_sort"].astype(float)
    cm = d["city_match"].isin(["t", "True", "true"])
    rev = d["tier"] == "review"

    final = pd.Series(np.where(d["tier"] == "auto_accept", "accept",
                      np.where(d["tier"] == "reject", "reject", None)), index=d.index, dtype=object)
    src = pd.Series(np.where(final == "accept", "original_auto_accept",
                    np.where(final == "reject", "original_reject", None)), index=d.index, dtype=object)

    sym = pd.Series([sym_match(a, b) for a, b in zip(d["source_name"], d["nu_name"])], index=d.index)
    city_sub = pd.Series(
        [str(a).upper() in str(b).upper() or str(b).upper() in str(a).upper()
         for a, b in zip(d["source_city"], d["nu_city"])], index=d.index)

    rules = [
        (rev & cm & (d["set_"] >= 95), "accept", "rule_same_city_superset"),
        (rev & ~cm & (d["sort_"] < 72), "reject", "rule_diff_city_weak_name"),
        (rev & cm & sym, "accept", "rule_symmetric_tokens_same_city"),
        (rev & ~cm & city_sub & (d["set_"] >= 90) & sym, "accept", "rule_city_subset"),
        (rev & ~cm, "reject", "rule_diff_city_no_subset"),
    ]
    for mask, verdict, label in rules:
        hit = mask & final.isna()
        final[hit], src[hit] = verdict, label

    queue = d[final.isna()]
    print(f"rules resolved {rev.sum() - len(queue)}/{rev.sum()} review rows; LLM queue: {len(queue)}")
    for i in range(0, len(queue), BATCH):
        chunk = queue.iloc[i: i + BATCH]
        lines = [f"{x.source_id}|{x.source_name}, {x.source_city}, {x.state} <> {x.nu_name}, {x.nu_city}"
                 for x in chunk.itertuples()]
        for dec in call_llm(lines):
            idx = d.index[d["source_id"] == dec["id"]]
            v = {"same": "accept", "different": "reject"}.get(dec["verdict"], "review")
            final[idx], src[idx] = v, f"llm_{MODEL}"

    d["final_tier"], d["decision_source"] = final.fillna("review"), src.fillna("llm_pending")
    d["CEEB_final"] = d["CEEB"].where(d["final_tier"] == "accept")
    out = path.replace(".csv", "_adjudicated.csv")
    d.drop(columns=["set_", "sort_"]).to_csv(out, index=False)
    print(out, d["final_tier"].value_counts().to_dict())


if __name__ == "__main__":
    main(sys.argv[1])
