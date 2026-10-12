import polars as pl
import pytest

from pipeline.clean import doc_publico_expr
from pipeline.io import check_no_cpf


def test_unmasked_cpf_is_refused():
    for cpf in ["12345678901", "123.456.789-01"]:
        with pytest.raises(ValueError, match="unmasked CPF"):
            check_no_cpf(pl.DataFrame({"fornecedor_doc": [cpf]}))


def test_masked_cpf_and_cnpj_pass():
    df = pl.DataFrame({"fornecedor_doc": ["12345678901", "12345678000190"]})
    check_no_cpf(df.with_columns(doc_publico_expr(pl.col("fornecedor_doc")).alias("fornecedor_doc")))
    # Only document columns are checked: an 11-digit number elsewhere is fine.
    check_no_cpf(pl.DataFrame({"telefone": ["11987654321"]}))
