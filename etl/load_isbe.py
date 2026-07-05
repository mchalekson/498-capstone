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
import db_utils

# Sheets to load (skip documentation/revision sheets)
SHEETS_TO_LOAD = [
    "General", "ACT", "IAR", "ISA", "CTE", "Discipline", "Finance", "KIDS", "SPED"
]


def clean_col(name: str) -> str:
    name = str(name).strip().lower()
    # "%" and "#" prefixes distinguish percent vs count columns that would
    # otherwise collide once punctuation is stripped (e.g. "% ... -Male" and
    # "# ... - Male" both reduce to "..._male")
    if name.startswith("%"):
        name = "pct_" + name[1:]
    elif name.startswith("#"):
        name = "count_" + name[1:]
    name = re.sub(r"[^\w]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name


def dedupe_columns(cols: list) -> list:
    """Suffix any remaining duplicate column names with _2, _3, ... """
    seen = {}
    result = []
    for c in cols:
        seen[c] = seen.get(c, 0) + 1
        result.append(c if seen[c] == 1 else f"{c}_{seen[c]}")
    return result


def truncate_columns(cols: list, maxlen: int = 63) -> list:
    """
    Postgres identifiers are truncated to 63 bytes (NAMEDATALEN). Some of
    these ISBE headers share a 63-byte prefix (several distinct names differ
    only after that point), which Postgres then rejects as a duplicate
    column. Truncate ourselves and disambiguate any resulting collisions,
    re-checking after each suffix attempt since shortening to fit a bigger
    suffix (_1 vs _12) can itself produce a new collision.
    """
    seen = set()
    result = []
    for c in cols:
        candidate = c[:maxlen]
        n = 1
        while candidate in seen:
            suffix = f"_{n}"
            candidate = c[: maxlen - len(suffix)] + suffix
            n += 1
        seen.add(candidate)
        result.append(candidate)
    return result


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
        df.columns = truncate_columns(dedupe_columns([clean_col(c) for c in df.columns]))
        df = df.dropna(how="all")

        table_name = f"isbe_{sheet.lower().replace(' ', '_').replace('(', '').replace(')', '')}"
        df.to_sql(table_name, engine, if_exists="replace", index=False,
                  method=db_utils.psql_insert_copy)
        print(f"    {len(df):,} rows → {table_name} ✓")


if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    load_isbe(engine)
