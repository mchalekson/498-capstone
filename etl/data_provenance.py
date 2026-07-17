"""
data_provenance.py -- when did WE pull each raw data source into this repo?

Separate from, and not a substitute for, the "vintage_as_of" field already in
docs/DATA_DICTIONARY.md: vintage_as_of is (where known) when the real-world data was
MEASURED (e.g. CRDC "School Year 2021-22"). This script answers a different, narrower
question: when did this team's repo actually receive that file, derived from git's own
commit history -- a fact we can always compute ourselves, without asking anyone.

Scoped to school/context data (NCES, Census, NAEP, ISBE, IB, College Board, CPS), not Bob's
NU org data -- excluded on request, and it already has its own separate vintage note
(NU_EXPORT_VINTAGE in build_modeling_dataset.py, from the export filename's timestamp).

Also excludes Sheng's combined schools export (data/updated-sheng/), not because it doesn't
matter but because it's gitignored (see "Ignore nested capstone repository") and was never
committed, so git has no record of when we received it. That's a real, separate limitation,
not glossed over: it also means CRDC data (which arrives bundled inside Sheng's export, not
loaded independently by this pipeline) inherits the same gap -- we can date the NCES/Census/
NAEP/ISBE/IB/CollegeBoard/CPS pulls below, but not CRDC's, via git history.

Run from the repo root:  python etl/data_provenance.py
Produces: docs/data_source_provenance.csv
"""
import os
import subprocess

import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# file (relative to repo root) -> human-readable source label, matching the naming already
# used in docs/DATA_DICTIONARY.md and data_dictionary_schools_org_enriched.csv
SOURCE_LABELS = {
    "data/CEEB-Crosswalk/oda_nces_ceeb_crosswalk.csv": "UC Boulder CEEB crosswalk",
    "data/CollegeBoard/collegeboard_ap_availability_2024-25.xlsx": "College Board AP (availability)",
    "data/CollegeBoard/collegeboard_ap_participation_2024-25.xlsx": "College Board AP (participation)",
    "data/CollegeBoard/collegeboard_ap_performance_2024-25.xlsx": "College Board AP (performance)",
    "data/CPS-Opportunity-Index/cps_opportunity_index_SY26.xlsx": "CPS Opportunity Index",
    "data/IB/ib_us.csv": "International Baccalaureate school directory",
    "data/ISBE/isbe_report_card_2025_glossary.pdf": "ISBE Report Card (glossary)",
    "data/ISBE/isbe_report_card_2025_illinois_schools.xlsx": "ISBE Report Card (IL schools)",
    "data/NAEP/naep_grade12_math_2024_national.xls": "NAEP grade 12 math (national)",
    "data/NAEP/naep_grade12_reading_2024_national.xls": "NAEP grade 12 reading (national)",
    "data/NAEP/naep_grade8_math_2024_bystate.xls": "NAEP grade 8 math (by state)",
    "data/NAEP/naep_grade8_reading_2024_bystate.xls": "NAEP grade 8 reading (by state)",
    "data/NCES/ELSI_csv_new_updated.csv": "NCES public HS grades 9-12 (12-digit ID re-pull)",
    "data/NCES/ELSI_public_school_grades_9-12_only.csv": "NCES public HS grades 9-12 (earlier pull)",
    "data/NCES/NCES_private_merged.csv": "NCES private schools (49-state PSS merge)",
    "data/NCES/NCES_private_merged.xlsx": "NCES private schools (49-state PSS merge, source xlsx)",
    "data/NCES/nces-private-schools.csv": "NCES private schools (ELSI)",
    "data/NCES/nces-public-schools.csv": "NCES public schools (CCD, 7-digit ID)",
    "data/US-Census-Saipe/2024-district-layout.txt.rtf": "Census SAIPE (file layout doc)",
    "data/US-Census-Saipe/census_saipe_poverty_2024_schooldistricts.xls": "Census SAIPE poverty",
    "data/US-Census/census_school_finances_FY2024_alldistricts.xlsx": "Census F-33 school finance (all districts)",
    "data/US-Census/census_school_finances_FY2024_summary.xlsx": "Census F-33 school finance (summary)",
}

UNTRACKED_NOTE = (
    "NOT tracked in git (data/updated-sheng/ is gitignored) -- no repo-provenance date "
    "available. Includes Sheng's combined schools export AND, bundled inside it, all CRDC "
    "columns (crdc_ap_offered, crdc_ap_enrollment, crdc_dual_enrollment, crdc_satact_takers, "
    "etc.) -- CRDC's freshness can't be dated from repo history for this reason, the same "
    "limitation as Bob's org export, just not previously flagged as such."
)


def _is_tracked(path):
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", path],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    return result.returncode == 0


def _commit_dates(path):
    first = subprocess.run(
        ["git", "log", "--follow", "--format=%ad", "--date=short", "--", path],
        cwd=REPO_ROOT, capture_output=True, text=True,
    ).stdout.strip().splitlines()
    last = subprocess.run(
        ["git", "log", "-1", "--format=%ad", "--date=short", "--", path],
        cwd=REPO_ROOT, capture_output=True, text=True,
    ).stdout.strip()
    return (first[-1] if first else None), (last or None)


def build_provenance_table():
    rows = []
    for rel_path, label in sorted(SOURCE_LABELS.items()):
        abs_path = os.path.join(REPO_ROOT, rel_path)
        if not os.path.exists(abs_path):
            rows.append({"file": rel_path, "source_dataset": label, "tracked_in_git": False,
                         "first_committed": None, "last_committed": None, "note": "file not found on disk"})
            continue
        if not _is_tracked(rel_path):
            rows.append({"file": rel_path, "source_dataset": label, "tracked_in_git": False,
                         "first_committed": None, "last_committed": None, "note": UNTRACKED_NOTE})
            continue
        first, last = _commit_dates(rel_path)
        rows.append({"file": rel_path, "source_dataset": label, "tracked_in_git": True,
                     "first_committed": first, "last_committed": last,
                     "note": "date of the last commit to this exact file, not the underlying "
                             "real-world data's own vintage (see vintage_as_of in DATA_DICTIONARY.md)"})

    # data/updated-sheng/ itself, called out explicitly even though its files aren't in
    # SOURCE_LABELS individually (they change name across pulls, e.g. Bob's timestamped export)
    rows.append({
        "file": "data/updated-sheng/* (Sheng's combined export, Bob's org export, EDA PDFs)",
        "source_dataset": "Sheng's combined schools export + Bob's NU org export",
        "tracked_in_git": False, "first_committed": None, "last_committed": None,
        "note": UNTRACKED_NOTE,
    })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = build_provenance_table()
    out_path = os.path.join(REPO_ROOT, "docs", "data_source_provenance.csv")
    df.to_csv(out_path, index=False)
    print(f"Wrote {out_path} ({len(df)} sources)")
    print(f"\nTracked in git (repo-provenance date available): {df['tracked_in_git'].sum()}")
    print(f"NOT tracked (gitignored, no repo-provenance date possible): {(~df['tracked_in_git']).sum()}")
