"""Cleaned, shared frames, memoised as Parquet in the cache directory.

Several loaders need the same cleaned CEAP / emendas tables. Parsing ~300 MB
of CSV once per loader would be wasteful, so each frame is built once and
reused for ``max_age``.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import timedelta

import polars as pl

from . import camara, ibge, matching, portal
from .http import CACHE_DIR, log

FRAMES = CACHE_DIR / "frames"


def memo(name: str, build: Callable[[], pl.DataFrame], max_age: timedelta = timedelta(hours=12)) -> pl.DataFrame:
    path = FRAMES / f"{name}.parquet"
    if path.exists() and time.time() - path.stat().st_mtime < max_age.total_seconds():
        return pl.read_parquet(path)
    t0 = time.time()
    df = build()
    FRAMES.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".parquet.part")
    df.write_parquet(tmp)
    tmp.replace(path)
    log(f"frame {name}: {df.height:,} rows in {time.time() - t0:.1f}s")
    return df


def municipios() -> pl.DataFrame:
    return memo("municipios", ibge.municipios, timedelta(days=7))


def deputados() -> pl.DataFrame:
    return memo("deputados", camara.deputados)


def deputados_historico() -> pl.DataFrame:
    return memo("deputados_historico", camara.deputados_historico, timedelta(days=7))


def ceap() -> pl.DataFrame:
    return memo("ceap", lambda: camara.ceap(camara.ceap_years()))


def ceis() -> pl.DataFrame:
    return memo("ceis", portal.ceis)


def _with_deputies(df: pl.DataFrame) -> pl.DataFrame:
    """Attach deputy ids to individual emendas (others are bancadas, committees, relator or senators)."""
    autores = df.filter(pl.col("tipo_grupo") == "Individual", pl.col("autor").is_not_null()).select("autor", "ano", "uf_code").unique()
    links = matching.match_autores(autores, deputados_historico())
    return df.join(links, on=["autor", "ano", "uf_code"], how="left", nulls_equal=True)


def emendas() -> pl.DataFrame:
    return memo("emendas", lambda: _with_deputies(portal.emendas(municipios()["code"])))


def emendas_favorecidos() -> pl.DataFrame:
    def build() -> pl.DataFrame:
        fav = matching.match_municipios(portal.emendas_favorecidos(), municipios())
        # The favorecido file has no UF code for the *emenda*; use the beneficiary's
        # UF for disambiguating author names.
        fav = fav.with_columns(pl.col("municipio_code").floordiv(100_000).cast(pl.Int32).alias("uf_code"))
        return _with_deputies(fav)

    return memo("emendas_favorecidos", build)
