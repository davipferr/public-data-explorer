"""Emendas parlamentares aggregated by year, type, author, destination UF/scope and function.

``pago_total`` = paid in the budget year + restos a pagar paid later. Individual
emendas are linked to Câmara deputies (``deputado_id``); unmatched individual
authors are senators.
"""

import polars as pl

from pipeline import frames
from pipeline.clean import uf_frame
from pipeline.io import emit_parquet

df = (
    frames.emendas()
    .group_by("ano", "tipo_grupo", "tipo", "autor", "deputado_id", "deputado_nome", "deputado_partido", "deputado_uf", "uf_code", "escopo", "funcao")
    .agg(
        pl.col("empenhado").sum().round(2),
        pl.col("pago_total").sum().round(2),
        pl.len().alias("linhas"),
    )
    .join(uf_frame().select("uf_code", pl.col("uf").alias("destino_uf")), on="uf_code", how="left")
    .with_columns(
        pl.when(pl.col("tipo_grupo") != "Individual")
        .then(pl.col("tipo_grupo"))
        .when(pl.col("deputado_id").is_not_null())
        .then(pl.lit("Deputado(a)"))
        .when(pl.col("autor").is_not_null())
        .then(pl.lit("Senador(a)"))
        .otherwise(pl.lit("Sem informação"))
        .alias("autor_tipo")
    )
    .sort("ano", "autor")
)
emit_parquet(df)
