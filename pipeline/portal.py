"""Portal da Transparência (CGU).

Two access paths:

* **Bulk downloads** (no key): ``portaldatransparencia.gov.br/download-de-dados/...``
  redirect to zipped Latin-1 CSVs. Used for emendas parlamentares and CEIS.
* **REST API** (needs a free key, sent as the ``chave-api-dados`` header and
  rate-limited). Used only for optional enrichment, and only at build time —
  the key is read from the environment and never written to any output.
"""

from __future__ import annotations

import io
import json
import os
import zipfile
from datetime import date, timedelta

import polars as pl

from .clean import br_number_expr, clean_text, cnpj_cpf_expr, decode_latin1, municipio_code_expr, norm_expr, uf_code_expr
from .http import ROOT, NotFound, RateLimiter, _cache_path, fetch, log

DOWNLOAD = "https://portaldatransparencia.gov.br/download-de-dados"
API = "https://api.portaldatransparencia.gov.br/api-de-dados"

VALORES = {
    "Valor Empenhado": "empenhado",
    "Valor Liquidado": "liquidado",
    "Valor Pago": "pago",
    "Valor Restos A Pagar Inscritos": "rp_inscritos",
    "Valor Restos A Pagar Cancelados": "rp_cancelados",
    "Valor Restos A Pagar Pagos": "rp_pagos",
}


def _read_zip_csv(blob: bytes, name: str | None = None) -> pl.DataFrame:
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        member = name or zf.namelist()[0]
        data = decode_latin1(zf.read(member))
    return pl.read_csv(io.BytesIO(data), separator=";", infer_schema=False)


# ---------------------------------------------------------------- emendas (bulk)


def emendas(municipios_validos: pl.Series) -> pl.DataFrame:
    """One row per (emenda, localidade, ação) with values as floats.

    ``pago`` counts payments made in the emenda's own budget year; payments made
    in later years show up in ``rp_pagos`` (restos a pagar). The total effectively
    paid is ``pago + rp_pagos``.
    """
    log("Portal: emendas parlamentares (bulk)")
    blob = fetch(f"{DOWNLOAD}/emendas-parlamentares/UNICO", suffix=".zip", max_age=timedelta(days=7))
    raw = _read_zip_csv(blob, "EmendasParlamentares.csv")
    sem_info = ["Sem informação", "S/I", ""]
    df = raw.select(
        pl.col("Código da Emenda").replace(sem_info, None).alias("emenda_id"),
        pl.col("Ano da Emenda").cast(pl.Int32).alias("ano"),
        clean_text(pl.col("Tipo de Emenda")).alias("tipo"),
        clean_text(pl.col("Nome do Autor da Emenda")).replace(sem_info, None).alias("autor"),
        clean_text(pl.col("Localidade de aplicação do recurso")).alias("localidade"),
        municipio_code_expr(pl.col("Código Município IBGE"), municipios_validos).alias("municipio_code"),
        uf_code_expr(pl.col("Código UF IBGE")).alias("uf_code"),
        clean_text(pl.col("Nome Função")).alias("funcao"),
        clean_text(pl.col("Nome Subfunção")).alias("subfuncao"),
        *[br_number_expr(pl.col(src)).fill_null(0).alias(dst) for src, dst in VALORES.items()],
    )
    return df.with_columns(
        (pl.col("pago") + pl.col("rp_pagos")).alias("pago_total"),
        pl.col("tipo").str.extract(r"^Emenda (?:de )?(\w+)").alias("tipo_grupo"),
        pl.when(pl.col("municipio_code").is_not_null())
        .then(pl.lit("Município"))
        .when(pl.col("localidade").str.ends_with("(UF)"))
        .then(pl.lit("Estado"))
        .when(pl.col("localidade") == "MÚLTIPLO")
        .then(pl.lit("Múltiplo"))
        .when(pl.col("localidade") == "Nacional")
        .then(pl.lit("Nacional"))
        .otherwise(pl.lit("Outro"))
        .alias("escopo"),
        norm_expr(pl.col("autor")).alias("autor_norm"),
    )


def emendas_favorecidos() -> pl.DataFrame:
    """Payments from emendas to each beneficiary, by month.

    Unlike the main file, this records *where the money landed* — but the
    municipality comes only as an uppercase name + UF ("SÃO LUIZ", "RR"), with no
    IBGE code. See ``matching.match_municipios``.
    """
    log("Portal: emendas por favorecido (bulk)")
    blob = fetch(f"{DOWNLOAD}/emendas-parlamentares/UNICO", suffix=".zip", max_age=timedelta(days=7))
    raw = _read_zip_csv(blob, "EmendasParlamentares_PorFavorecido.csv")
    sem_info = ["Sem informação", "S/I", "Inválido", "-1", ""]
    return raw.select(
        pl.col("Código da Emenda").alias("emenda_id"),
        clean_text(pl.col("Nome do Autor da Emenda")).replace(sem_info, None).alias("autor"),
        clean_text(pl.col("Tipo de Emenda")).alias("tipo"),
        pl.col("Ano/Mês").str.slice(0, 4).cast(pl.Int32, strict=False).alias("ano"),
        pl.col("Ano/Mês").str.slice(4, 2).cast(pl.Int32, strict=False).alias("mes"),
        cnpj_cpf_expr(pl.col("Código do Favorecido")).alias("favorecido_doc"),
        clean_text(pl.col("Favorecido")).alias("favorecido"),
        clean_text(pl.col("Natureza Jurídica")).alias("natureza_juridica"),
        clean_text(pl.col("Tipo Favorecido")).str.replace(r"Genéric$", "Genérica").alias("tipo_favorecido"),
        pl.col("UF Favorecido").replace(sem_info, None).alias("uf"),
        clean_text(pl.col("Município Favorecido")).replace(sem_info, None).alias("municipio_nome"),
        br_number_expr(pl.col("Valor Recebido")).fill_null(0).alias("valor"),
    ).with_columns(
        pl.col("tipo").str.extract(r"^Emenda (?:de )?(\w+)").alias("tipo_grupo"),
        norm_expr(pl.col("autor")).alias("autor_norm"),
    )


# ------------------------------------------------------------------- CEIS (bulk)


def ceis(lookback_days: int = 10) -> pl.DataFrame:
    """Cadastro de Empresas Inidôneas e Suspensas — latest daily snapshot.

    Today's file usually isn't published until later in the day (403), so walk
    back until one exists.
    """
    for back in range(lookback_days):
        day = (date.today() - timedelta(days=back)).strftime("%Y%m%d")
        try:
            blob = fetch(f"{DOWNLOAD}/ceis/{day}", suffix=".zip", max_age=None)
            log(f"Portal: CEIS snapshot {day}")
            break
        except NotFound:
            continue
    else:
        raise RuntimeError(f"No CEIS snapshot in the last {lookback_days} days")

    raw = _read_zip_csv(blob)
    return raw.select(
        pl.lit(f"{day[:4]}-{day[4:6]}-{day[6:]}").alias("snapshot"),
        cnpj_cpf_expr(pl.col("CPF OU CNPJ DO SANCIONADO")).alias("doc"),
        pl.col("TIPO DE PESSOA").alias("tipo_pessoa"),
        clean_text(pl.col("NOME DO SANCIONADO")).alias("nome"),
        clean_text(pl.col("CATEGORIA DA SANÇÃO")).alias("categoria"),
        pl.col("DATA INÍCIO SANÇÃO").str.to_date("%d/%m/%Y", strict=False).alias("inicio"),
        pl.col("DATA FINAL SANÇÃO").str.to_date("%d/%m/%Y", strict=False).alias("fim"),
        clean_text(pl.col("ÓRGÃO SANCIONADOR")).alias("orgao"),
        clean_text(pl.col("ABRAGÊNCIA DA SANÇÃO")).alias("abrangencia"),
    ).filter(pl.col("doc").is_not_null())


# --------------------------------------------------------------- REST API (key)


def api_key() -> str | None:
    """Read the key from the environment or a local, git-ignored .env file."""
    key = os.environ.get("PORTAL_TRANSPARENCIA_API_KEY")
    env = ROOT / ".env"
    if not key and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "PORTAL_TRANSPARENCIA_API_KEY":
                key = value.strip().strip("'\"")
    return key or None


class PortalApi:
    """Minimal client. CGU documents ~90 req/min in daytime (more at night); we
    default to 80 to stay under it. Responses are cached on disk per request, so
    an interrupted build resumes where it stopped."""

    def __init__(self, key: str, per_minute: int = int(os.environ.get("PORTAL_API_RPM", "80"))):
        self._headers = {"chave-api-dados": key, "Accept": "application/json"}
        self._limiter = RateLimiter(per_minute)

    def get(self, path: str, params: dict, max_age: timedelta | None = None) -> list | dict:
        # Only rate-limit real network calls, not cache hits.
        cached = _cache_path(f"{API}/{path}", params, ".json")
        if not cached.exists():
            self._limiter.wait()
        return json.loads(fetch(f"{API}/{path}", params=params, headers=self._headers, suffix=".json", max_age=max_age))

    def bolsa_familia_municipio(self, mes_ano: str, codigo_ibge: int) -> list[dict]:
        """Novo Bolsa Família paid in one municipality in one month (``mes_ano`` = "YYYYMM")."""
        return self.get("novo-bolsa-familia-por-municipio", {"mesAno": mes_ano, "codigoIbge": codigo_ibge, "pagina": 1})  # type: ignore[return-value]


def bolsa_familia(municipios: pl.DataFrame, mes_ano: str) -> pl.DataFrame:
    """Bolsa Família by municipality for one month via the API (≈5.6k calls ≈ 70 min at 80 rpm,
    cached afterwards)."""
    key = api_key()
    if not key:
        raise PermissionError("PORTAL_TRANSPARENCIA_API_KEY not set")
    api = PortalApi(key)
    rows = []
    codes = municipios["code"].to_list()
    for i, code in enumerate(codes, 1):
        if i % 250 == 0:
            log(f"  Bolsa Família {mes_ano}: {i}/{len(codes)}")
        for item in api.bolsa_familia_municipio(mes_ano, code):
            rows.append(
                {
                    "municipio_code": int(item["municipio"]["codigoIBGE"]),
                    "mes_ano": mes_ano,
                    "valor": float(item["valor"]),
                    "beneficiarios": int(item["quantidadeBeneficiados"]),
                }
            )
    return pl.DataFrame(rows, schema={"municipio_code": pl.Int32, "mes_ano": pl.String, "valor": pl.Float64, "beneficiarios": pl.Int32})


def default_bf_month() -> str:
    """Payments are published with a lag; three months back is a safe default."""
    d = date.today().replace(day=1)
    for _ in range(3):
        d = (d - timedelta(days=1)).replace(day=1)
    return os.environ.get("PORTAL_BF_MES", d.strftime("%Y%m"))

