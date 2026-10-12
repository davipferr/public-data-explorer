"""IBGE: SIDRA aggregates, the municipality list and the mesh (malhas) API.

SIDRA's v3 API returns deeply nested JSON:

    [ {variavel, unidade, resultados: [ {classificacoes, series: [
        {localidade: {id, nome, nivel}, serie: {"2022": "1581196", ...}}
    ]} ]} ]

``sidra()`` flattens that into one tidy row per (variable, place, period).
"""

from __future__ import annotations

import json
from datetime import timedelta

import polars as pl

from .clean import clean_text, norm_expr, uf_frame
from .http import fetch, log

BASE = "https://servicodados.ibge.gov.br/api"
MUNICIPIOS_URL = f"{BASE}/v1/localidades/municipios"

# SIDRA's special symbols (see "Sinais convencionais" on sidra.ibge.gov.br).
#   "-"   numeric zero, not from rounding      -> 0
#   ".." not applicable, "..." not available, "X" suppressed (confidentiality) -> null
SIDRA_ZERO = {"-"}


def sidra(
    agregado: int,
    variaveis: list[int] | int,
    periodos: str = "-1",
    nivel: str = "N6",
    localidades: str = "all",
    classificacao: str | None = None,
) -> pl.DataFrame:
    """Fetch a SIDRA aggregate and return it in long format.

    ``periodos`` follows the API syntax: "-1" = latest, "2019-2023", "2022|2025"...
    ``nivel``: N1 Brasil, N2 região, N3 UF, N6 município.
    """
    vars_ = "|".join(map(str, variaveis)) if isinstance(variaveis, list) else str(variaveis)
    url = f"{BASE}/v3/agregados/{agregado}/periodos/{periodos}/variaveis/{vars_}"
    params = {"localidades": f"{nivel}[{localidades}]"}
    if classificacao:
        params["classificacao"] = classificacao
    log(f"SIDRA {agregado} vars={vars_} periodos={periodos} {nivel}")
    payload = json.loads(fetch(url, params=params, suffix=".json"))

    rows = []
    for var in payload:
        for res in var["resultados"]:
            cats = {c["nome"]: next(iter(c["categoria"].values())) for c in res.get("classificacoes", [])}
            for s in res["series"]:
                loc = s["localidade"]
                for periodo, valor in s["serie"].items():
                    rows.append(
                        {
                            "variavel_id": int(var["id"]),
                            "variavel": var["variavel"],
                            "unidade": var["unidade"],
                            "localidade_id": int(loc["id"]),
                            "localidade": loc["nome"],
                            "nivel": loc["nivel"]["id"],
                            "periodo": periodo,
                            "valor_raw": valor,
                            **cats,
                        }
                    )
    df = pl.DataFrame(rows, infer_schema_length=None)
    return df.with_columns(
        pl.when(pl.col("valor_raw").is_in(list(SIDRA_ZERO)))
        .then(pl.lit(0.0))
        .otherwise(pl.col("valor_raw").cast(pl.Float64, strict=False))
        .alias("valor"),
        pl.col("periodo").cast(pl.Int32, strict=False).alias("ano"),
    )


def municipios() -> pl.DataFrame:
    """Official municipality list with UF and region.

    Newly created municipalities can arrive with ``microrregiao: null`` (e.g.
    Boa Esperança do Norte-MT, created in 2025, after microregions were frozen),
    so the UF is taken from the newer "região imediata" hierarchy when needed.
    """
    data = json.loads(fetch(MUNICIPIOS_URL, suffix=".json", max_age=timedelta(days=30)))
    rows = []
    for m in data:
        uf = None
        if m.get("microrregiao"):
            uf = m["microrregiao"]["mesorregiao"]["UF"]
        elif m.get("regiao-imediata"):
            uf = m["regiao-imediata"]["regiao-intermediaria"]["UF"]
        rows.append({"code": m["id"], "nome": m["nome"], "uf_code": uf["id"] if uf else m["id"] // 100_000})
    df = pl.DataFrame(rows).with_columns(
        pl.col("code").cast(pl.Int32),
        pl.col("uf_code").cast(pl.Int32),
        clean_text(pl.col("nome")),
    )
    return df.join(uf_frame(), on="uf_code", how="left").with_columns(norm_expr(pl.col("nome")).alias("nome_norm"))


def malha_request(intrarregiao: str, qualidade: str = "minima", localidade: str = "paises/BR") -> tuple[str, dict]:
    """URL and query parameters of a /api/v3/malhas request."""
    return f"{BASE}/v3/malhas/{localidade}", {"intrarregiao": intrarregiao, "qualidade": qualidade, "formato": "application/json"}


def malha(intrarregiao: str, qualidade: str = "minima", localidade: str = "paises/BR") -> bytes:
    """TopoJSON mesh from /api/v3/malhas. Features carry ``codarea`` (the IBGE code)."""
    url, params = malha_request(intrarregiao, qualidade, localidade)
    log(f"malha {localidade} intrarregiao={intrarregiao} qualidade={qualidade}")
    return fetch(url, params=params, suffix=".topojson", max_age=timedelta(days=90))


def wide(df: pl.DataFrame, name: str) -> pl.DataFrame:
    """(localidade_id, ano, valor) -> (code, ano, <name>)."""
    return df.select(
        pl.col("localidade_id").cast(pl.Int32).alias("code"),
        pl.col("ano"),
        pl.col("valor").alias(name),
    )
