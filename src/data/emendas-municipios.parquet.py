"""Money from emendas received by beneficiaries located in each municipality, by year.

Built from the "por favorecido" file, whose municipality is a name + UF; names
are linked to IBGE codes by exact match, a rename table, then fuzzy matching
within the UF (see pipeline/matching.py).
"""

import polars as pl

from pipeline import frames
from pipeline.io import emit_parquet

df = (
    frames.emendas_favorecidos()
    .filter(pl.col("municipio_code").is_not_null())
    .group_by("municipio_code", "ano", "tipo_grupo", "deputado_id")
    .agg(pl.col("valor").sum().round(2))
    .filter(pl.col("valor") != 0)
    .sort("municipio_code", "ano")
)
emit_parquet(df)
