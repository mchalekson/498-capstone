"""
Shared fast bulk-load helper for pandas.to_sql().

pandas' default insert methods (single-row, or method="multi" batching a
handful of rows per INSERT) are slow for the wide/large tables in this
pipeline (e.g. ISBE sheets at ~900 columns, NCES tables at 100k+ rows).
Postgres's native COPY protocol is dramatically faster for bulk loads, so
every load/clean/combine step uses to_sql(..., method=psql_insert_copy)
instead of method="multi".
"""

import csv
from io import StringIO


def psql_insert_copy(table, conn, keys, data_iter):
    dbapi_conn = conn.connection
    with dbapi_conn.cursor() as cur:
        buf = StringIO()
        writer = csv.writer(buf)
        writer.writerows(data_iter)
        buf.seek(0)

        columns = ", ".join(f'"{k}"' for k in keys)
        table_name = f'"{table.schema}"."{table.name}"' if table.schema else f'"{table.name}"'
        sql = f"COPY {table_name} ({columns}) FROM STDIN WITH CSV"
        cur.copy_expert(sql=sql, file=buf)
