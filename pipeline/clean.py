"""Cleaning helpers shared by every source.

Brazilian public data has a handful of recurring problems:

* text in mixed encodings and inconsistent accents/case ("São Paulo", "SAO PAULO");
* numbers in Brazilian format ("1.234,56") next to plain ones ("1234.56");
* IBGE codes written in several widths (UF "33" vs "3300000"; municipality with
  or without the 7th check digit);
* municipalities that didn't exist in older years.
"""

from __future__ import annotations

import unicodedata

import polars as pl

# IBGE UF codes. Hardcoded because they are stable and tiny.
UFS: list[tuple[int, str, str, str]] = [
    (11, "RO", "Rondônia", "Norte"),
    (12, "AC", "Acre", "Norte"),
    (13, "AM", "Amazonas", "Norte"),
    (14, "RR", "Roraima", "Norte"),
    (15, "PA", "Pará", "Norte"),
    (16, "AP", "Amapá", "Norte"),
    (17, "TO", "Tocantins", "Norte"),
    (21, "MA", "Maranhão", "Nordeste"),
    (22, "PI", "Piauí", "Nordeste"),
    (23, "CE", "Ceará", "Nordeste"),
    (24, "RN", "Rio Grande do Norte", "Nordeste"),
    (25, "PB", "Paraíba", "Nordeste"),
    (26, "PE", "Pernambuco", "Nordeste"),
    (27, "AL", "Alagoas", "Nordeste"),
    (28, "SE", "Sergipe", "Nordeste"),
    (29, "BA", "Bahia", "Nordeste"),
    (31, "MG", "Minas Gerais", "Sudeste"),
    (32, "ES", "Espírito Santo", "Sudeste"),
    (33, "RJ", "Rio de Janeiro", "Sudeste"),
    (35, "SP", "São Paulo", "Sudeste"),
    (41, "PR", "Paraná", "Sul"),
    (42, "SC", "Santa Catarina", "Sul"),
    (43, "RS", "Rio Grande do Sul", "Sul"),
    (50, "MS", "Mato Grosso do Sul", "Centro-Oeste"),
    (51, "MT", "Mato Grosso", "Centro-Oeste"),
    (52, "GO", "Goiás", "Centro-Oeste"),
    (53, "DF", "Distrito Federal", "Centro-Oeste"),
]


def uf_frame() -> pl.DataFrame:
    return pl.DataFrame(
        UFS,
        schema={"uf_code": pl.Int32, "uf": pl.String, "uf_nome": pl.String, "regiao": pl.String},
        orient="row",
    )


# --------------------------------------------------------------------------- text


def strip_accents(text: str) -> str:
    """'São João d'Aliança' -> 'Sao Joao d'Alianca' (pure-Python version, for tests/one-offs)."""
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def normalize_name(text: str | None) -> str | None:
    """Canonical key for matching names across sources (Python version of ``norm_expr``)."""
    if text is None:
        return None
    out = strip_accents(text).upper()
    out = "".join(c if c.isalnum() else " " for c in out)
    return " ".join(out.split()) or None


def norm_expr(expr: pl.Expr) -> pl.Expr:
    """Vectorised ``normalize_name``: strip accents, uppercase, drop punctuation, squeeze spaces.

    "  Alta Floresta D'Oeste " and "ALTA FLORESTA D OESTE" both become
    "ALTA FLORESTA D OESTE".
    """
    return (
        expr.str.normalize("NFD")
        .str.replace_all(r"\p{Mn}", "")
        .str.to_uppercase()
        .str.replace_all(r"[^A-Z0-9]+", " ")
        .str.strip_chars()
        .replace("", None)
    )


def clean_text(expr: pl.Expr) -> pl.Expr:
    """Trim, squeeze internal whitespace and turn empty strings into nulls."""
    return expr.str.strip_chars().str.replace_all(r"\s+", " ").replace("", None)


def decode_latin1(data: bytes) -> bytes:
    """Re-encode a Windows-1252/Latin-1 CSV as UTF-8 so Polars can read it.

    Polars only reads UTF-8. CGU's bulk files (Portal da Transparência) are
    Latin-1; decoding as cp1252 is a superset that also maps the "smart quotes"
    that occasionally appear in free-text fields.
    """
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:]
    try:
        data.decode("utf-8")
        return data  # already UTF-8
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace").encode("utf-8")


# ------------------------------------------------------------------------ numbers


def br_number_expr(expr: pl.Expr) -> pl.Expr:
    """Parse numbers that may be in Brazilian or plain format into Float64.

    Rules (string in, float out):
      "1.234,56" -> 1234.56   comma present: dots are thousands separators
      "1300000,00" -> 1300000.0
      "1.234.567" -> 1234567  several dots: thousands separators
      "1.234" -> 1234         one dot followed by exactly 3 digits: thousands
      "1467.5" -> 1467.5      otherwise a dot is the decimal separator (CEAP files)
      "", "-", "S/I" -> null
    """
    s = expr.cast(pl.String).str.strip_chars().str.replace_all(r"[R$\s]", "")
    has_comma = s.str.contains(",", literal=True)
    thousands_only = s.str.contains(r"^-?\d{1,3}(\.\d{3})+$")
    normalised = (
        pl.when(has_comma)
        .then(s.str.replace_all(".", "", literal=True).str.replace(",", ".", literal=True))
        .when(thousands_only)
        .then(s.str.replace_all(".", "", literal=True))
        .otherwise(s)
    )
    return normalised.cast(pl.Float64, strict=False)


def parse_br_number(text: str | None) -> float | None:
    """Scalar version of ``br_number_expr`` (handy in tests and notebooks)."""
    return pl.select(br_number_expr(pl.lit(text, dtype=pl.String))).item()


# -------------------------------------------------------------------- IBGE codes


def uf_code_expr(expr: pl.Expr) -> pl.Expr:
    """Accept UF codes as 33, "33", "3300000" or a 7-digit municipality code -> Int32 33.

    Anything that isn't a real UF ("-1" for national, "Sem informação") -> null.
    """
    digits = expr.cast(pl.String).str.strip_chars()
    code = (
        pl.when(digits.str.contains(r"^\d{2}(\d{5})?$"))
        .then(digits.str.slice(0, 2))
        .otherwise(None)
        .cast(pl.Int32, strict=False)
    )
    return pl.when(code.is_in([u[0] for u in UFS])).then(code).otherwise(None)


def municipio_code_expr(expr: pl.Expr, valid: pl.Series) -> pl.Expr:
    """Normalise municipality codes to IBGE's 7-digit form.

    Some datasets (DATASUS, older TSE/CGU files) use 6 digits without the check
    digit. The 7th digit isn't trivially derivable for every code, so instead we
    map via the first 6 digits of the current official list. Codes that still
    don't match (e.g. "S/I", or municipalities that no longer exist) become null.
    """
    six_to_seven = dict(zip((valid // 10).to_list(), valid.to_list(), strict=True))
    digits = expr.cast(pl.String).str.replace_all(r"\D", "").cast(pl.Int64, strict=False)
    return (
        pl.when(digits.is_in(valid.implode()))
        .then(digits)
        .when(digits < 1_000_000)
        .then(digits.replace_strict(six_to_seven, default=None, return_dtype=pl.Int64))
        .otherwise(None)
        .cast(pl.Int32)
    )


def cnpj_cpf_expr(expr: pl.Expr) -> pl.Expr:
    """Keep only the digits of a CNPJ/CPF ("12.345.678/0001-90" -> "12345678000190")."""
    return expr.str.replace_all(r"\D", "").replace("", None)
