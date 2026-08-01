"""
build_ope_ceeb_junction.py -- OPE(ID) <-> CEEB junction for postsecondary institutions
(Secondary goal: "Establish a junction mapping system linking OPE and CEEB codes").

WHY THIS IS A SEPARATE, SOURCE-GATED BUILDER
--------------------------------------------
Every other crosswalk in this repo is anchored on *high schools*, where we hold the federal
IDs ourselves (NCES 7/12-digit, PSS) and match them to CEEB. OPE IDs identify *colleges*
(postsecondary), a population that appears nowhere in our school-level sources -- so this
junction cannot be derived from what we already load. It needs an external college-level
source that carries **both** an OPE ID and a CEEB code (see docs/OPE_CEEB_JUNCTION.md for the
sourcing options and why no single free federal table provides both).

This script is therefore written to *consume* that source once supplied, not to invent it. It
runs in two modes:

  1. direct   -- a single file already carrying OPEID + CEEB columns (e.g. the PESC/SPEEDE
                 College Crosswalk Table, CollegeSource TES export, or the community Higher-Ed
                 School Code Crosswalk). Normalize, dedupe, emit the junction.
  2. match    -- (interface stub) a federal file with OPEID (College Scorecard / IPEDS) plus a
                 separate CEEB college list, joined by fuzzy name+location the way
                 build_ceeb_crosswalk.py already matches high schools. Left as a documented hook
                 so the wiring exists the moment both inputs land.

If no source is found it exits 0 with guidance -- so run_all.py / the dashboard degrade
cleanly rather than erroring, exactly like the optional stages already do.

CEEB codes are recycled when institutions close/merge (confirmed in the sourcing research), so
we keep code-reuse *visible*: duplicates on either side are flagged, never silently collapsed.

Run:
  python build_ope_ceeb_junction.py --source PATH.csv --ope-col OPEID --ceeb-col CEEB \
         --version v1 --outdir ../csv_exports
"""
import argparse
import datetime as dt
import os
import sys

import pandas as pd


def _norm_ope(s):
    """OPE IDs are 8-digit (6-digit institution + 2-digit branch), often stored with a leading
    zero or as an int. Keep as zero-padded text so the leading zero survives."""
    s = s.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    return s.str.zfill(8).where(s.str.len().le(8), s)


def _norm_ceeb(s):
    """CEEB is 6-digit, zero-padded -- the same leading-zero hazard we handle for high schools."""
    return s.astype(str).str.strip().str.replace(r"\.0$", "", regex=True).str.zfill(6)


def build_direct(src, ope_col, ceeb_col, name_col=None):
    df = pd.read_csv(src, dtype=str, low_memory=False)
    for c in (ope_col, ceeb_col):
        if c not in df.columns:
            sys.exit(f"Column {c!r} not in {src}. Present: {list(df.columns)[:20]}...")

    out = pd.DataFrame({
        "opeid": _norm_ope(df[ope_col]),
        "ceeb": _norm_ceeb(df[ceeb_col]),
    })
    if name_col and name_col in df.columns:
        out["institution_name"] = df[name_col].str.strip()
    out = out.dropna(subset=["opeid", "ceeb"])
    out = out[(out["opeid"] != "0" * 8) & (out["ceeb"] != "0" * 6)].drop_duplicates()

    # Make code reuse visible rather than collapsing it.
    out["ope_maps_to_n_ceeb"] = out.groupby("opeid")["ceeb"].transform("nunique")
    out["ceeb_maps_to_n_ope"] = out.groupby("ceeb")["opeid"].transform("nunique")
    out["is_one_to_one"] = (out["ope_maps_to_n_ceeb"] == 1) & (out["ceeb_maps_to_n_ope"] == 1)

    n_amb = int((~out["is_one_to_one"]).sum())
    print(f"  {len(out):,} OPE<->CEEB pairs "
          f"({out['opeid'].nunique():,} distinct OPE, {out['ceeb'].nunique():,} distinct CEEB); "
          f"{n_amb:,} pairs are many-to-* (flagged is_one_to_one=False, code reuse)")
    return out


def build_match():
    # Interface hook for the fuzzy path (federal OPEID file + CEEB college list, matched on
    # name+location). Deliberately not implemented until both inputs exist -- see the module
    # docstring and docs/OPE_CEEB_JUNCTION.md. Reuse build_ceeb_crosswalk.py's matcher here.
    sys.exit("match mode needs a federal OPEID source AND a CEEB college list; neither is "
             "present. See docs/OPE_CEEB_JUNCTION.md for the sourcing plan.")


DEFAULT_SOURCES = [
    # Drop a real crosswalk at any of these and it is picked up automatically.
    "../data/OPE-CEEB/ope_ceeb_source.csv",
    "../data/OPE-CEEB/college_code_crosswalk.csv",
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", help="CSV carrying both an OPE ID and a CEEB column (direct mode)")
    p.add_argument("--ope-col", default="OPEID")
    p.add_argument("--ceeb-col", default="CEEB")
    p.add_argument("--name-col", default="INSTNM")
    p.add_argument("--mode", choices=["direct", "match"], default="direct")
    p.add_argument("--version", default="v1")
    p.add_argument("--outdir", default="../csv_exports")
    args = p.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    src = args.source
    if not src:
        for cand in DEFAULT_SOURCES:
            cand = os.path.join(here, cand)
            if os.path.exists(cand):
                src = cand
                break

    if args.mode == "match":
        junction = build_match()
    elif not src or not os.path.exists(src):
        print("No OPE<->CEEB source found. This junction needs an external college-level file "
              "carrying both an OPE ID and a CEEB code.\n"
              "  Provide one with --source PATH (direct mode), or drop it at "
              "data/OPE-CEEB/ope_ceeb_source.csv.\n"
              "  See docs/OPE_CEEB_JUNCTION.md for where to get one.")
        return 0
    else:
        print(f"Building OPE<->CEEB junction (direct) from {os.path.basename(src)}...")
        junction = build_direct(src, args.ope_col, args.ceeb_col, args.name_col)

    date_tag = dt.date.today().isoformat()
    out = os.path.join(args.outdir, f"ope_ceeb_junction_{args.version}_{date_tag}.csv")
    junction.to_csv(out, index=False)
    print(f"Wrote {out} ({len(junction):,} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
