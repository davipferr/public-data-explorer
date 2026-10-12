import polars as pl
import pytest

from pipeline.clean import (
    br_number_expr,
    doc_publico_expr,
    decode_latin1,
    municipio_code_expr,
    norm_expr,
    normalize_name,
    parse_br_number,
    uf_code_expr,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.234,56", 1234.56),
        ("1300000,00", 1300000.0),
        ("0,00", 0.0),
        ("-394200,00", -394200.0),
        ("1.234.567", 1234567.0),
        ("1.234", 1234.0),
        ("1467.5", 1467.5),
        ("1467", 1467.0),
        ("R$ 2.500,10", 2500.10),
        ("", None),
        ("S/I", None),
        (None, None),
    ],
)
def test_parse_br_number(raw, expected):
    assert parse_br_number(raw) == expected


def test_br_number_expr_column():
    df = pl.DataFrame({"v": ["1.234,56", "12.5", None]})
    assert df.select(br_number_expr(pl.col("v")))["v"].to_list() == [1234.56, 12.5, None]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("São Paulo", "SAO PAULO"),
        ("  Alta Floresta D'Oeste ", "ALTA FLORESTA D OESTE"),
        ("ITAMBÉ - BA", "ITAMBE BA"),
        ("Pinto  Bandeira", "PINTO BANDEIRA"),
        ("", None),
    ],
)
def test_normalize_name_python_and_polars_agree(raw, expected):
    assert normalize_name(raw) == expected
    assert pl.select(norm_expr(pl.lit(raw))).item() == expected


def test_uf_code_expr():
    df = pl.DataFrame({"c": ["3300000", "33", "3550308", None, "-1", "Sem informação", "99", "1"]})
    assert df.select(uf_code_expr(pl.col("c")))["c"].to_list() == [33, 33, 35, None, None, None, None, None]


def test_municipio_code_expr_fixes_six_digit_codes():
    valid = pl.Series([3550308, 3304557, 1100015])
    df = pl.DataFrame({"c": ["3550308", "355030", "330455", "S/I", "9999999", None]})
    out = df.select(municipio_code_expr(pl.col("c"), valid))["c"].to_list()
    assert out == [3550308, 3550308, 3304557, None, None, None]


def test_decode_latin1():
    latin = "Código;Município\n1;São Paulo\n".encode("cp1252")
    assert decode_latin1(latin).decode("utf-8").startswith("Código")
    utf8_bom = b"\xef\xbb\xbf" + "Ação".encode()
    assert decode_latin1(utf8_bom) == "Ação".encode()


def test_doc_publico_masks_cpf_and_formats_cnpj():
    docs = pl.Series(["12345678000190", "12345678901", "123", None])
    out = pl.select(doc_publico_expr(pl.lit(docs))).to_series().to_list()
    assert out == ["12.345.678/0001-90", "***.456.789-**", "123", None]
