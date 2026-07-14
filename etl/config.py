import os

# PostgreSQL connection — set these as env vars or edit directly
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "capstone")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

# CEEB-anchored "NU master" school list (see data/NU-Master/README.md).
# build_ceeb_crosswalk.py picks this up automatically.
NU_MASTER_PATH = os.getenv("NU_MASTER_PATH", os.path.join(DATA_DIR, "NU-Master", "nu_master.xlsx"))

# Sheng's nationwide schools export, already enriched with a CEEB column via
# the UC Boulder crosswalk (see data/CEEB-Crosswalk/README.md) — distinct
# from the NCES<->CEEB junction build_ceeb_crosswalk.py builds from our own
# NCES tables.
SCHOOLS_CEEB_PATH = os.getenv(
    "SCHOOLS_CEEB_PATH",
    os.path.join(DATA_DIR, "updated-sheng", "schools_combined_enriched_ceeb.csv"),
)
