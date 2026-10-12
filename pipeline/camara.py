"""Câmara dos Deputados: deputies and CEAP (Cota para o Exercício da Atividade Parlamentar).

The REST API (dadosabertos.camara.leg.br/api/v2) paginates at most 100 items per
page, and expenses are per-deputy per-year — thousands of calls. The bulk files
are far easier: one zipped CSV per year with every expense of every deputy.
We only use the API for the current roster (party, UF, photo), ~7 pages.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import date, timedelta

import polars as pl

from .clean import br_number_expr, clean_text, cnpj_cpf_expr, norm_expr
from .http import NotFound, fetch, log
from .schema import require_columns

API = "https://dadosabertos.camara.leg.br/api/v2"
BULK_DEPUTADOS = "https://dadosabertos.camara.leg.br/arquivos/deputados/csv/deputados.csv"
BULK_CEAP = "https://www.camara.leg.br/cotas/Ano-{year}.csv.zip"

# Legislature 57 runs Feb 2023 - Jan 2027.
LEGISLATURA_ATUAL = 57
LEGISLATURA_INICIO = {55: 2015, 56: 2019, 57: 2023, 58: 2027}

# Raw fields each source must provide (checked right after parsing).
ROSTER_COLUMNS = ["id", "nome", "siglaPartido", "siglaUf", "urlFoto"]
DEPUTADOS_BULK_COLUMNS = ["uri", "nomeCivil", "siglaSexo", "dataNascimento", "idLegislaturaInicial", "idLegislaturaFinal"]
CEAP_COLUMNS = [
    "ideCadastro",
    "txNomeParlamentar",
    "sgPartido",
    "sgUF",
    "numAno",
    "numMes",
    "datEmissao",
    "numSubCota",
    "txtDescricao",
    "txtFornecedor",
    "txtCNPJCPF",
    "vlrDocumento",
    "vlrGlosa",
    "vlrLiquido",
    "vlrRestituicao",
    "ideDocumento",
    "urlDocumento",
]

# Short display labels for CEAP sub-quotas (numSubCota). The raw descriptions are
# long, uppercase and have changed wording over the years, so the code is the
# stable key and these labels are what the site shows.
CATEGORIAS = {
    1: "Escritório de apoio",
    3: "Combustíveis",
    4: "Consultorias e pesquisas",
    5: "Divulgação da atividade",
    8: "Segurança",
    9: "Passagens aéreas (reembolso)",
    10: "Telefonia",
    11: "Serviços postais",
    12: "Assinaturas de publicações",
    13: "Alimentação",
    14: "Hospedagem",
    15: "Locação de veículos",
    40: "Auxílio-moradia (complemento)",
    119: "Fretamento de aeronaves",
    120: "Locação de veículos",
    121: "Fretamento de embarcações",
    122: "Táxi, pedágio e estacionamento",
    123: "Passagens terrestres/fluviais",
    137: "Cursos e eventos",
    145: "Tokens e certificados digitais",
    998: "Passagens aéreas (SIGEPA)",
    999: "Passagens aéreas (RPA)",
}


def _api_pages(path: str, params: dict) -> list[dict]:
    """Follow the API's ``links[rel=next]`` until exhausted."""
    out: list[dict] = []
    url: str | None = f"{API}/{path}"
    query: dict | None = {"itens": 100, **params}
    while url:
        payload = json.loads(
            fetch(url, params=query, headers={"Accept": "application/json"}, suffix=".json", max_age=timedelta(days=1))
        )
        out.extend(payload["dados"])
        url = next((link["href"] for link in payload.get("links", []) if link["rel"] == "next"), None)
        query = None  # the "next" href already carries the query string
    return out


def deputados() -> pl.DataFrame:
    """Every deputy who served in the current legislature, with civil data from the bulk file."""
    log("Câmara: deputados (API, current legislature)")
    roster = pl.DataFrame(_api_pages("deputados", {"idLegislatura": LEGISLATURA_ATUAL, "ordem": "ASC", "ordenarPor": "nome"}))
    roster = require_columns(roster, ROSTER_COLUMNS, f"Câmara API deputados (legislatura {LEGISLATURA_ATUAL})").select(
        pl.col("id").cast(pl.Int32).alias("deputado_id"),
        clean_text(pl.col("nome")).alias("nome"),
        pl.col("siglaPartido").alias("partido"),
        pl.col("siglaUf").alias("uf"),
        pl.col("urlFoto").alias("foto"),
    ).unique("deputado_id", keep="last")

    log("Câmara: deputados (bulk CSV, all legislatures)")
    bulk = pl.read_csv(io.BytesIO(fetch(BULK_DEPUTADOS, suffix=".csv")), separator=";", infer_schema=False)
    bulk = require_columns(bulk, DEPUTADOS_BULK_COLUMNS, "Câmara deputados.csv").select(
        pl.col("uri").str.extract(r"/(\d+)$").cast(pl.Int32).alias("deputado_id"),
        clean_text(pl.col("nomeCivil")).alias("nome_civil"),
        pl.col("siglaSexo").alias("sexo"),
        pl.col("dataNascimento").str.to_date(strict=False).alias("nascimento"),
        pl.col("idLegislaturaInicial").cast(pl.Int32).alias("leg_inicial"),
        pl.col("idLegislaturaFinal").cast(pl.Int32).alias("leg_final"),
    )

    # Currently in office? The API without idLegislatura lists only deputies em exercício.
    em_exercicio = {d["id"] for d in _api_pages("deputados", {})}

    return (
        roster.join(bulk, on="deputado_id", how="left")
        .with_columns(
            pl.col("deputado_id").is_in(list(em_exercicio)).alias("em_exercicio"),
            norm_expr(pl.col("nome")).alias("nome_norm"),
        )
        .sort("nome")
    )


def deputados_historico() -> pl.DataFrame:
    """Parliamentary names for all deputies since legislature 55 (used to match emendas authors).

    The bulk file has civil names only, so parliamentary names come from the API
    roster of each legislature.
    """
    frames = []
    for leg in (55, 56, 57):
        log(f"Câmara: roster legislatura {leg}")
        rows = _api_pages("deputados", {"idLegislatura": leg})
        frames.append(
            require_columns(pl.DataFrame(rows), ROSTER_COLUMNS, f"Câmara API deputados (legislatura {leg})").select(
                pl.col("id").cast(pl.Int32).alias("deputado_id"),
                clean_text(pl.col("nome")).alias("nome"),
                pl.col("siglaPartido").alias("partido"),
                pl.col("siglaUf").alias("uf"),
                pl.lit(leg, dtype=pl.Int32).alias("legislatura"),
            )
        )
    return pl.concat(frames).unique(["deputado_id", "legislatura"]).with_columns(norm_expr(pl.col("nome")).alias("nome_norm"))


def ceap_raw(year: int) -> pl.DataFrame | None:
    try:
        blob = fetch(BULK_CEAP.format(year=year), suffix=".zip", max_age=timedelta(days=3 if year >= date.today().year - 1 else 90))
    except NotFound:
        log(f"  CEAP {year}: not published")
        return None
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        data = zf.read(zf.namelist()[0])
    log(f"  CEAP {year}: {len(data) / 1e6:.0f} MB")
    # Checked per year: the concat in ``ceap`` is relaxed, so a column renamed in
    # one year would otherwise just turn into nulls for that year.
    return require_columns(pl.read_csv(io.BytesIO(data), separator=";", infer_schema=False), CEAP_COLUMNS, f"Câmara CEAP {year}")


def ceap(years: list[int]) -> pl.DataFrame:
    """One clean row per expense document."""
    frames = [df for y in years if (df := ceap_raw(y)) is not None]
    raw = pl.concat(frames, how="diagonal_relaxed")
    df = raw.select(
        pl.col("ideCadastro").replace("", None).cast(pl.Int32, strict=False).alias("deputado_id"),
        clean_text(pl.col("txNomeParlamentar")).alias("nome"),
        clean_text(pl.col("sgPartido")).alias("partido"),
        pl.col("sgUF").replace({"NA": None, "": None}).alias("uf"),
        pl.col("numAno").cast(pl.Int32).alias("ano"),
        pl.col("numMes").cast(pl.Int32).alias("mes"),
        pl.col("datEmissao").str.slice(0, 10).str.to_date(strict=False).alias("data_emissao"),
        pl.col("numSubCota").cast(pl.Int32).alias("categoria_code"),
        clean_text(pl.col("txtDescricao")).alias("categoria_raw"),
        clean_text(pl.col("txtFornecedor")).alias("fornecedor"),
        cnpj_cpf_expr(pl.col("txtCNPJCPF")).alias("fornecedor_doc"),
        br_number_expr(pl.col("vlrDocumento")).alias("valor_documento"),
        br_number_expr(pl.col("vlrGlosa")).fill_null(0).alias("valor_glosa"),
        br_number_expr(pl.col("vlrLiquido")).alias("valor_liquido"),
        br_number_expr(pl.col("vlrRestituicao")).fill_null(0).alias("valor_restituicao"),
        pl.col("ideDocumento").alias("documento_id"),
        pl.col("urlDocumento").alias("url_documento"),
    )
    # Net spending = liquid value minus later refunds (refunds come as separate rows
    # with valor_liquido 0). Two sign quirks:
    #  * airline tickets (998/999) have negative rows for cancellations/credits: keep;
    #  * the housing-allowance complement (40) is booked as a *negative* liquid value
    #    with a positive document value — it's a debit against the quota, i.e. spending.
    # Leadership offices ("LID.GOV-CD", "LIDERANÇA DO PT"...) spend from the quota
    # without a deputy id; keep them but flag them.
    df = df.with_columns(
        pl.when(pl.col("categoria_code") == 40)
        .then(pl.col("valor_liquido").abs())
        .otherwise(pl.col("valor_liquido") - pl.col("valor_restituicao"))
        .alias("valor"),
        pl.col("deputado_id").is_null().alias("lideranca"),
        pl.col("categoria_code").replace_strict(CATEGORIAS, default=None, return_dtype=pl.String).alias("categoria"),
        pl.col("fornecedor_doc").str.len_chars().replace_strict({14: "CNPJ", 11: "CPF"}, default="Outro", return_dtype=pl.String).alias("fornecedor_tipo"),
    )
    # Unknown codes fall back to the most common raw description for that code.
    fallback = df.group_by("categoria_code").agg(pl.col("categoria_raw").drop_nulls().mode().first().str.to_titlecase().alias("_fb"))
    return df.join(fallback, on="categoria_code", how="left").with_columns(pl.coalesce("categoria", "_fb").alias("categoria")).drop("_fb", "categoria_raw")


def ceap_years() -> list[int]:
    return list(range(LEGISLATURA_INICIO[LEGISLATURA_ATUAL], date.today().year + 1))
