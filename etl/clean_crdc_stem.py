"""
clean_crdc_stem.py -- advanced-STEM course availability from CRDC 2021-22 course files.

The Week-5 client meeting named "STEM classes available" as a school-comparison signal. The
CRDC course-offering files (data/updated-sheng/2021-22-crdc-data/SCH/) carry, per school
(keyed by COMBOKEY = 12-digit NCESSCH), the number of class sections offered for individual
advanced courses -- `SCH_MATHCLASSES_*` / `SCH_SCICLASSES_*`. This aggregates the four clearly
rigor-discriminating advanced courses (Calculus, Advanced Mathematics, Chemistry, Physics --
Biology/Algebra/Geometry are near-universal and carry little signal) into a per-school
availability count.

Encoding: classes > 0 -> offered (1); classes == 0 -> not offered (0); classes < 0 -> reserve
code (-3/-5/-9: suppressed or not-applicable, overwhelmingly non-high-schools) -> NaN.

CRDC is public-school-only by federal design, so this joins to public schools via nces_id_12
and is ~0% for private schools -- a structural gap, consistent with the rest of the CRDC layer.

Run:  python clean_crdc_stem.py            # writes crdc_stem_clean.csv
"""
import os

import numpy as np
import pandas as pd

CRDC_SCH_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "data", "updated-sheng", "2021-22-crdc-data", "SCH")

# file -> (classes-offered column, output flag name)
COURSES = {
    "Calculus.csv": ("SCH_MATHCLASSES_CALC", "calculus_offered"),
    "Advanced Mathematics.csv": ("SCH_MATHCLASSES_ADVM", "advmath_offered"),
    "Chemistry.csv": ("SCH_SCICLASSES_CHEM", "chemistry_offered"),
    "Physics.csv": ("SCH_SCICLASSES_PHYS", "physics_offered"),
}


def offered_flag(series):
    """classes>0 -> 1.0 ; classes==0 -> 0.0 ; classes<0 (reserve) -> NaN."""
    v = pd.to_numeric(series, errors="coerce")
    return np.where(v < 0, np.nan, (v > 0).astype(float))


def build(crdc_dir=CRDC_SCH_DIR):
    out = None
    for fname, (col, flag) in COURSES.items():
        path = os.path.join(crdc_dir, fname)
        d = pd.read_csv(path, usecols=["COMBOKEY", col], dtype={"COMBOKEY": str}, low_memory=False)
        d[flag] = offered_flag(d[col])
        d = d[["COMBOKEY", flag]].rename(columns={"COMBOKEY": "nces_id_12"})
        out = d if out is None else out.merge(d, on="nces_id_12", how="outer")
    flag_cols = [f for _, f in COURSES.values()]
    # count of the 4 advanced courses offered; NaN only if the school reported none of them
    out["stem_advanced_offered"] = out[flag_cols].sum(axis=1, min_count=1)
    return out


if __name__ == "__main__":
    out = build()
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "csv_exports",
                            "crdc_stem_clean.csv")
    out.to_csv(out_path, index=False)
    hs_like = out["stem_advanced_offered"].notna()
    print(f"Wrote {out_path}: {len(out):,} schools, {int(hs_like.sum()):,} with any advanced-STEM signal")
    print("stem_advanced_offered distribution (0-4, among reporting schools):")
    print(out.loc[hs_like, "stem_advanced_offered"].value_counts().sort_index().to_string())
    for _, flag in COURSES.values():
        print(f"   {flag:20} offered at {int((out[flag] == 1).sum()):,} schools")
