"""Top suppliers per deputy (up to 25 each), for the deputy profile page."""

import duckdb

from pipeline import frames
from pipeline.io import emit_parquet

ceap = frames.ceap()
df = duckdb.sql(
    """
    WITH t AS (
        SELECT deputado_id, fornecedor_doc, mode(fornecedor) AS fornecedor, mode(categoria) AS categoria,
               round(sum(valor), 2) AS valor, count(*) AS documentos
        FROM ceap
        WHERE deputado_id IS NOT NULL AND fornecedor_doc IS NOT NULL
        GROUP BY ALL
    )
    SELECT * FROM t
    QUALIFY row_number() OVER (PARTITION BY deputado_id ORDER BY valor DESC) <= 25
    ORDER BY deputado_id, valor DESC
    """
).pl()
emit_parquet(df)
