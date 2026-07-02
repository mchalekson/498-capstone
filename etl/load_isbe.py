"""
Load ISBE Illinois Report Card data into PostgreSQL.

Each sheet in the Excel file maps to its own table:
  isbe_general, isbe_act, isbe_iar, isbe_isa, isbe_cte, isbe_discipline,
  isbe_finance, isbe_kids, isbe_sped

The RCDTS code is the Illinois state school identifier.
NCESSCH cross-walk can be done via NCES Common Core of Data if needed.
"""

import os
import re
import pandas as pd
from sqlalchemy import create_engine
from config import DATABASE_URL, DATA_DIR

# Sheets to load (skip documentation/revision sheets)
SHEETS_TO_LOAD = [
    "General", "ACT", "IAR", "ISA", "CTE", "Discipline", "Finance", "KIDS", "SPED"
]


def clean_col(name: str) -> str:
    name = str(name).strip().lower()
    name = re.sub(r"[^\w]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name


def load_isbe(engine):
    path = os.path.join(DATA_DIR, "ISBE", "isbe_report_card_2025_illinois_schools.xlsx")
    xl = pd.ExcelFile(path)
    print(f"ISBE file has sheets: {xl.sheet_names}")

    for sheet in SHEETS_TO_LOAD:
        if sheet not in xl.sheet_names:
            # Try case-insensitive match
            match = next((s for s in xl.sheet_names if s.lower() == sheet.lower()), None)
            if match is None:
                print(f"  Sheet '{sheet}' not found, skipping")
                continue
            sheet = match

        print(f"  Reading sheet '{sheet}'...")
        df = xl.parse(sheet)
        df.columns = [clean_col(c) for c in df.columns]
        df = df.dropna(how="all")

        table_name = f"isbe_{sheet.lower().replace(' ', '_').replace('(', '').replace(')', '')}"
        df.to_sql(table_name, engine, if_exists="replace", index=False,
                  method="multi", chunksize=500)
        print(f"    {len(df):,} rows → {table_name} ✓")


if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    load_isbe(engine)
