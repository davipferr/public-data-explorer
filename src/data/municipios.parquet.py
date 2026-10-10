"""Municipalities with population (Censo 2022 + latest estimate) and GDP (PIB municipal).

SIDRA tables:
  4709 v93   População residente — Censo 2022
  6579 v9324 População residente estimada (annual estimates)
  5938 v37   PIB a preços correntes (R$ mil)
"""

import polars as pl

from pipeline import frames, ibge
from pipeline.io import emit_parquet

mun = frames.municipios()

censo = ibge.wide(ibge.sidra(4709, 93, "2022"), "pop_2022").drop("ano")
# SIDRA rejects mixing explicit periods with "-1" (latest), hence two calls.
est = ibge.wide(ibge.sidra(6579, 9324, "-1"), "pop_est")
ano_est = est["ano"].max()
est = est.drop("ano")
est_2024 = ibge.wide(ibge.sidra(6579, 9324, "2024"), "pop_2024").drop("ano")
pib = ibge.wide(ibge.sidra(5938, 37, "-1"), "pib_mil")
ano_pib = pib["ano"].max()

df = (
    mun.join(censo, on="code", how="left")
    .join(est, on="code", how="left")
    .join(est_2024, on="code", how="left")
    .join(pib.drop("ano"), on="code", how="left")
    .with_columns(
        pl.lit(ano_est, dtype=pl.Int32).alias("pop_est_ano"),
        pl.lit(ano_pib, dtype=pl.Int32).alias("pib_ano"),
        (pl.col("pib_mil") * 1000).alias("pib"),
    )
    # IBGE publishes no population estimate for 2023 (the census disrupted the
    # series), so per-capita GDP for 2023 uses the midpoint of Censo 2022 and the
    # 2024 estimate as its denominator.
    .with_columns(
        pl.when(pl.col("pib_ano") == 2023)
        .then(pl.col("pib") / ((pl.col("pop_2022") + pl.col("pop_2024")) / 2))
        .otherwise(pl.col("pib") / pl.col("pop_2022"))
        .alias("pib_pc"),
        (pl.col("pop_est") / pl.col("pop_2022") - 1).alias("crescimento"),
    )
    .drop("pib_mil", "pop_2024", "nome_norm")
    .sort("code")
)
emit_parquet(df)
