"""Top suppliers per deputy (up to 25 each), for the deputy profile page."""

import duckdb
import polars as pl

from pipeline import frames
from pipeline.clean import doc_publico_expr
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
# Mask CPFs (people) after the joins/grouping, which need the full digits.
emit_parquet(df.with_columns(doc_publico_expr(pl.col("fornecedor_doc")).alias("fornecedor_doc")))
