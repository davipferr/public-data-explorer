import polars as pl
import pytest

from pipeline.schema import SchemaError, require_columns


def test_passes_through_when_columns_present():
    df = pl.DataFrame({"a": [1], "b": [2], "extra": [3]})
    assert require_columns(df, ["a", "b"], "test") is df


def test_missing_column_names_source_and_suggests_rename():
    df = pl.DataFrame({"Código da Emenda": ["1"], "Valor Pago (R$)": ["0"]})
    with pytest.raises(SchemaError) as exc:
        require_columns(df, ["Código da Emenda", "Valor Pago"], "Portal emendas")
    msg = str(exc.value)
    assert msg.startswith("Portal emendas: 1 expected column(s) missing")
    assert "'Valor Pago' (did you mean 'Valor Pago (R$)'?)" in msg


def test_alias_is_renamed_to_expected_name():
    # Today CGU misspells the column; the day they fix it, both must work.
    typo = pl.DataFrame({"ABRAGÊNCIA DA SANÇÃO": ["x"]})
    fixed = pl.DataFrame({"ABRANGÊNCIA DA SANÇÃO": ["x"]})
    aliases = {"ABRAGÊNCIA DA SANÇÃO": "ABRANGÊNCIA DA SANÇÃO"}
    for df in (typo, fixed):
        out = require_columns(df, ["ABRANGÊNCIA DA SANÇÃO"], "CEIS", aliases=aliases)
        assert out.columns == ["ABRANGÊNCIA DA SANÇÃO"]


def test_empty_file_is_an_error():
    with pytest.raises(SchemaError, match="at least 1 row"):
        require_columns(pl.DataFrame({"a": []}), ["a"], "empty")
