"""CEAP spending aggregated to deputy x month x category.

Row-level data (~800k documents) is too big to ship; this keeps every dimension
the site filters on. Party and UF are as recorded at the time of each expense.
"""

import polars as pl

from pipeline import frames
from pipeline.io import emit_parquet

df = (
    frames.ceap()
    .group_by("deputado_id", "nome", "partido", "uf", "lideranca", "ano", "mes", "categoria_code", "categoria")
    .agg(pl.col("valor").sum().round(2), pl.len().alias("documentos"))
    .sort("ano", "mes", "nome", "categoria_code")
)
emit_parquet(df)
