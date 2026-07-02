"""
Load IB school data into PostgreSQL.

Table created:
  ib_schools — one row per IB-authorized US school (PK: school_id)

Note: IB uses its own school_id (IBO number), not NCESSCH.
A fuzzy join to nces_public_schools on name + state can be done
via the views/analysis layer.
"""

import os
import pandas as pd
from sqlalchemy import create_engine, text
from config import DATABASE_URL, DATA_DIR


def load_ib(engine):
    path = os.path.join(DATA_DIR, "IB", "ib_us.csv")
    print("Reading IB schools...")
    df = pd.read_csv(path)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    print(f"  {len(df):,} rows, {len(df.columns)} columns")
    df.to_sql("ib_schools", engine, if_exists="replace", index=False,
              method="multi", chunksize=500)
    print("  Loaded ib_schools ✓")

    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE ib_schools ADD PRIMARY KEY (school_id)"))
        conn.commit()


if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    load_ib(engine)
