"""Novo Bolsa Família by municipality (Portal da Transparência REST API).

Needs PORTAL_TRANSPARENCIA_API_KEY (environment or .env). Without a key this
emits an empty table with the right schema and the site explains how to enable
it. The key is only used here, at build time; it never reaches the browser.
"""

import polars as pl

from pipeline import frames, portal
from pipeline.http import log
from pipeline.io import emit_parquet

if portal.api_key():
    df = portal.bolsa_familia(frames.municipios(), portal.default_bf_month())
else:
    log("bolsa-familia: PORTAL_TRANSPARENCIA_API_KEY not set — emitting an empty table")
    df = pl.DataFrame(schema={"municipio_code": pl.Int32, "mes_ano": pl.String, "valor": pl.Float64, "beneficiarios": pl.Int32})
emit_parquet(df)
