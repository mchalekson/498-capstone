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
# Not present in the repo as of this writing — Bob's copy is out of date and
# needs replacing. Once a current file is dropped at this path (or
# NU_MASTER_PATH is pointed elsewhere), build_ceeb_crosswalk.py picks it up
# automatically; until then that step no-ops.
NU_MASTER_PATH = os.getenv("NU_MASTER_PATH", os.path.join(DATA_DIR, "NU-Master", "nu_master.csv"))
