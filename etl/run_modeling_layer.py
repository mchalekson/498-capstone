"""
Rebuild the modeling layer end to end (build_features -> ... -> benchmarking).

Why this is a separate entry point from run_all.py
--------------------------------------------------
run_all.py is idempotent: re-running it rebuilds the same tables from the same
raw sources. The modeling layer is not, because each build script stamps its
output with today's date (`modeling_dataset_v1_<today>.csv`). Folding these
steps into run_all.py would therefore mint a brand-new dataset every time
anyone rebuilt the database, quietly moving the "frozen" dataset that the
report's Section 4 numbers were computed against.

So rebuilding is deliberate and explicit: you run this script, you get new
date-tagged artifacts, and you decide whether that becomes the new freeze
(by bumping FROZEN_VERSION in load_modeling_layer.py and updating the docs).
run_all.py only ever *loads* the existing freeze.

The order below is the real dependency chain, which until now existed only as
tribal knowledge -- each step consumes the previous step's output:

    schools_org_all.csv                 (stage 3, from the database)
      -> build_features.py              -> schools_features.csv
      -> build_modeling_dataset.py      -> modeling_dataset_<ver>_<date>.csv
                                           + data_dictionary_modeling_dataset.csv
      -> build_rigor_classification.py  -> rigor_classification_<ver>_<date>.csv
                                           + rigor_sensitivity_<ver>_<date>.csv
      -> build_clustering.py            -> clustering_<ver>_<date>.csv
                                           + pca_loadings, gap_statistic
      -> build_benchmarking.py          -> benchmarking_<ver>_<date>.csv

build_clustering and build_benchmarking both branch off rigor_classification;
neither consumes the other.

Run:
    python run_modeling_layer.py                  # into csv_exports/, version v1
    python run_modeling_layer.py --version v2     # cut a new freeze
    python run_modeling_layer.py --dry-run        # print the sequence, run nothing
"""

import argparse
import datetime as dt
import glob
import os
import subprocess
import sys

ETL_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_EXPORTS_DIR = os.path.join(ETL_DIR, "..", "csv_exports")


def _dated(stem, version, outdir):
    """Resolve a step's date-tagged output, newest first.

    Steps are chained by filename, and a build run just before midnight can tag
    its output with a different date than the run that consumes it, so resolve
    by glob rather than assuming today's date.
    """
    matches = sorted(glob.glob(os.path.join(outdir, f"{stem}_{version}_*.csv")))
    return matches[-1] if matches else None


def plan(version, outdir):
    """The build sequence, as (label, argv-builder) pairs.

    Each argv-builder is a callable so that a step's input path is resolved at
    the moment it runs -- the previous step's output filename isn't known until
    that step has actually written it.
    """
    joined = os.path.join(outdir, "schools_org_all.csv")
    features = os.path.join(outdir, "schools_features.csv")

    return [
        ("build_features", lambda: [
            "build_features.py", joined,
        ]),
        ("build_modeling_dataset", lambda: [
            "build_modeling_dataset.py", features,
            "--version", version, "--outdir", outdir,
        ]),
        ("build_rigor_classification", lambda: [
            "build_rigor_classification.py", _dated("modeling_dataset", version, outdir),
            "--version", version, "--outdir", outdir,
        ]),
        ("build_clustering", lambda: [
            "build_clustering.py", _dated("rigor_classification", version, outdir),
            "--version", version, "--outdir", outdir,
        ]),
        ("build_benchmarking", lambda: [
            "build_benchmarking.py", _dated("rigor_classification", version, outdir),
            "--version", version, "--outdir", outdir,
        ]),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", default="v1",
                        help="Freeze version tag to stamp outputs with (default: v1)")
    parser.add_argument("--outdir", default=CSV_EXPORTS_DIR,
                        help="Directory to read inputs from and write outputs into")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the sequence without running anything")
    args = parser.parse_args()

    outdir = os.path.abspath(args.outdir)
    os.makedirs(outdir, exist_ok=True)

    joined = os.path.join(outdir, "schools_org_all.csv")
    if not os.path.exists(joined) and not args.dry_run:
        sys.exit(f"Missing {joined} -- that's stage 3's output. Run run_all.py first, "
                 f"or point --outdir at a directory that has it.")

    print(f"Rebuilding modeling layer: version={args.version}  outdir={outdir}")
    print(f"Outputs will be tagged {args.version}_{dt.date.today().isoformat()}.")
    print("This does NOT change what the database treats as frozen -- load_modeling_layer.py\n"
          "pins an exact tag. To promote this build to the freeze, set FREEZE_TAG there.")

    failed = []
    for label, argv_fn in plan(args.version, outdir):
        argv = argv_fn()
        print(f"\n{'=' * 50}\n[MODELING] {label}\n{'=' * 50}")

        if any(a is None for a in argv):
            print(f"  ERROR: {label} has an unresolved input -- a previous step "
                  f"didn't produce its output.")
            failed.append(label)
            continue

        printable = " ".join(os.path.basename(a) if os.path.sep in str(a) else str(a)
                             for a in argv)
        print(f"  $ python {printable}")
        if args.dry_run:
            continue

        # cwd=ETL_DIR because the build scripts import sibling modules (config,
        # db_utils) directly, and build_features.py resolves its funding inputs
        # relative to the input file it's handed, not to cwd.
        result = subprocess.run([sys.executable] + argv, cwd=ETL_DIR)
        if result.returncode != 0:
            print(f"  ERROR: {label} exited {result.returncode}")
            failed.append(label)
            break  # later steps consume this one's output; don't run them on stale input

    # build_features.py hardcodes its output to cwd; move it where the chain expects.
    stray = os.path.join(ETL_DIR, "schools_features.csv")
    if os.path.exists(stray) and not args.dry_run:
        os.replace(stray, os.path.join(outdir, "schools_features.csv"))

    print(f"\n{'=' * 50}")
    if args.dry_run:
        print("Dry run — nothing executed.")
    elif failed:
        print("Modeling layer failed at:\n  " + "\n  ".join(failed))
        sys.exit(1)
    else:
        tag = f"{args.version}_{dt.date.today().isoformat()}"
        print(f"Modeling layer rebuilt ✓  (tag {tag})")
        print("\nThe database still points at the previous freeze. To promote this build:")
        print(f'  1. set FREEZE_TAG = "{tag}" in load_modeling_layer.py')
        print("  2. python load_modeling_layer.py")


if __name__ == "__main__":
    main()
