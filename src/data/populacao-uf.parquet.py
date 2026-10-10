"""Population by UF over time: annual estimates (SIDRA 6579) plus census counts (4709, 2022)."""

import polars as pl

from pipeline import ibge
from pipeline.clean import uf_frame
from pipeline.io import emit_parquet


def by_uf(df: pl.DataFrame, fonte: str) -> pl.DataFrame:
    return df.select(
        pl.col("localidade_id").cast(pl.Int32).alias("uf_code"),
        "ano",
        pl.col("valor").alias("populacao"),
        pl.lit(fonte).alias("fonte"),
    )


est = by_uf(ibge.sidra(6579, 9324, "all", nivel="N3"), "Estimativa")
censo = by_uf(ibge.sidra(4709, 93, "2022", nivel="N3"), "Censo")
df = pl.concat([est, censo]).join(uf_frame(), on="uf_code").drop_nulls("populacao").sort("uf_code", "ano")
emit_parquet(df)
