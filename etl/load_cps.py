"""
Load CPS Opportunity Index into PostgreSQL.

Elementary and High School data are stacked into one table.

Table created:
  cps_opportunity_index — one row per CPS school (PK: school_id)

Note: uses CPS School ID, not NCESSCH. Join to NCES via name/address matching
or the CPS-NCES crosswalk if available.
"""

import os
import pandas as pd
from sqlalchemy import create_engine, text
from config import DATABASE_URL, DATA_DIR


def load_cps(engine):
    path = os.path.join(DATA_DIR, "CPS-Opportunity-Index", "cps_opportunity_index_SY26.xlsx")
    xl = pd.ExcelFile(path)

    frames = []
    for sheet in ["Elementary Schools", "High Schools"]:
        if sheet in xl.sheet_names:
            df = xl.parse(sheet)
            df.columns = [c.strip().lower().replace(" ", "_").replace("/", "_") for c in df.columns]
            frames.append(df)
            print(f"  {sheet}: {len(df)} rows")

    combined = pd.concat(frames, ignore_index=True)
    print(f"  Total: {len(combined):,} rows")
    combined.to_sql("cps_opportunity_index", engine, if_exists="replace", index=False,
                    method="multi", chunksize=500)
    print("  Loaded cps_opportunity_index ✓")

    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE cps_opportunity_index ADD PRIMARY KEY (school_id)"))
        conn.commit()


if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    load_cps(engine)
