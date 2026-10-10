"""Record linkage across sources: municipality names -> IBGE codes, emenda authors -> deputies.

DuckDB does the heavy joins: it queries Polars frames in place (zero-copy via
Arrow) and SQL window functions make "pick the best candidate" rules readable.
"""

from __future__ import annotations

import difflib

import duckdb
import polars as pl

from .camara import LEGISLATURA_INICIO
from .clean import norm_expr, uf_frame

# Municipalities that were renamed (or whose old name is still used by some
# agencies). Keys and values are ``normalize_name`` keys, scoped by UF.
# Spelling variants (Itapagé/Itapajé, Poxoréo/Poxoréu...) are left to the fuzzy
# step; only real renamings, which fuzzy matching can't guess, belong here.
MUNICIPIO_ALIASES: dict[tuple[str, str], str] = {
    ("SP", "EMBU"): "EMBU DAS ARTES",
    ("RN", "ACU"): "ASSU",
    ("RN", "PRESIDENTE JUSCELINO"): "SERRA CAIADA",
    ("RN", "AUGUSTO SEVERO"): "CAMPO GRANDE",
    ("RR", "SAO LUIZ"): "SAO LUIZ DO ANAUA",
    ("TO", "FORTALEZA DO TABOCAO"): "TABOCAO",
    ("PB", "SERIDO"): "SAO VICENTE DO SERIDO",
    ("PE", "BELEM DE SAO FRANCISCO"): "BELEM DO SAO FRANCISCO",
    ("RS", "SANTANA DO LIVRAMENTO"): "SANT ANA DO LIVRAMENTO",
    ("RN", "ARES"): "AREZ",
}

FUZZY_CUTOFF = 0.85


def match_municipios(df: pl.DataFrame, municipios: pl.DataFrame, uf_col: str = "uf", name_col: str = "municipio_nome") -> pl.DataFrame:
    """Add ``municipio_code`` and ``match`` ("exato" | "alias" | "aproximado" | null).

    Strategy: exact match on (UF, normalised name) -> alias table -> closest
    name within the same UF (difflib ratio >= FUZZY_CUTOFF). Matching is done on
    the distinct (UF, name) pairs, then joined back.
    """
    pairs = df.select(pl.col(uf_col).alias("uf"), norm_expr(pl.col(name_col)).alias("k")).unique().drop_nulls()
    ref = municipios.select("uf", pl.col("nome_norm").alias("k"), pl.col("code").alias("municipio_code"))
    exact = set(ref.select("uf", "k").iter_rows())
    names_by_uf: dict[str, list[str]] = {}
    for uf, k in exact:
        names_by_uf.setdefault(uf, []).append(k)

    rows = []
    for uf, k in pairs.iter_rows():
        if (uf, k) in exact:
            rows.append((uf, k, k, "exato"))
        elif (uf, k) in MUNICIPIO_ALIASES:
            rows.append((uf, k, MUNICIPIO_ALIASES[(uf, k)], "alias"))
        elif best := difflib.get_close_matches(k, names_by_uf.get(uf, []), n=1, cutoff=FUZZY_CUTOFF):
            rows.append((uf, k, best[0], "aproximado"))
    lookup = (
        pl.DataFrame(rows, schema={"uf": pl.String, "k": pl.String, "k_ref": pl.String, "match": pl.String}, orient="row")
        .join(ref, left_on=["uf", "k_ref"], right_on=["uf", "k"], how="inner")
        .select("uf", "k", "municipio_code", "match")
    )
    return (
        df.with_columns(norm_expr(pl.col(name_col)).alias("_k"))
        .join(lookup, left_on=[uf_col, "_k"], right_on=["uf", "k"], how="left")
        .drop("_k")
    )


def author_key(expr: pl.Expr) -> pl.Expr:
    """Matching key for parliamentary names.

    * drops the "(EX-PARLAMENTAR FULANO NOS TERMOS DO ART. 78 ...)" tail used when
      an emenda passes to a successor — the first name is the current author;
    * drops particles (DA, DE, DO, DOS, DAS, E), so "Glaustin da Fokus" ==
      "GLAUSTIN FOKUS".
    """
    base = norm_expr(expr).str.replace(r" EX PARLAMENTAR .*$", "")
    return base.str.replace_all(r"\b(DA|DE|DO|DAS|DOS|E)\b", "").str.replace_all(r"\s+", " ").str.strip_chars()


def legislatura_for_year(year_col: str) -> str:
    """SQL CASE mapping a calendar year to its legislature number."""
    cases = " ".join(f"WHEN {year_col} >= {start} THEN {leg}" for leg, start in sorted(LEGISLATURA_INICIO.items(), reverse=True))
    return f"CASE {cases} ELSE 54 END"


def match_autores(autores: pl.DataFrame, deputados_hist: pl.DataFrame) -> pl.DataFrame:
    """Map distinct (autor, ano, uf_code) to a Câmara deputy id.

    Emendas for budget year Y are proposed in Y-1, so the author must have been
    a deputy in the legislature covering Y-1. When a parliamentary name is
    shared by two deputies (it happens: "Bebeto", "Dr. João"), prefer the one
    from that legislature and from the same UF as the emenda.
    Authors with no match are senators, committees or bancadas.
    """
    a = autores.with_columns(author_key(pl.col("autor")).alias("key"))
    d = deputados_hist.with_columns(author_key(pl.col("nome")).alias("key"))
    d = d.join(uf_frame().select("uf", "uf_code"), on="uf", how="left")
    con = duckdb.connect()
    con.register("a", a)
    con.register("d", d)
    return con.sql(
        f"""
        WITH cand AS (
            SELECT a.autor, a.ano, a.uf_code AS emenda_uf, d.deputado_id, d.nome, d.partido, d.uf,
                   d.legislatura,
                   ({legislatura_for_year("a.ano - 1")}) AS leg_proposta,
                   row_number() OVER (
                       PARTITION BY a.autor, a.ano, a.uf_code
                       ORDER BY
                           abs(d.legislatura - ({legislatura_for_year("a.ano - 1")})),
                           (d.uf_code IS NOT DISTINCT FROM a.uf_code) DESC,
                           d.legislatura DESC
                   ) AS rk
            FROM a JOIN d ON a.key = d.key
        )
        SELECT autor, ano, emenda_uf AS uf_code, deputado_id, nome AS deputado_nome,
               partido AS deputado_partido, uf AS deputado_uf
        FROM cand
        WHERE rk = 1 AND abs(legislatura - leg_proposta) <= 1
        """
    ).pl()
