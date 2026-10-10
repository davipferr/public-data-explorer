import polars as pl

from pipeline.matching import author_key, match_autores, match_municipios

MUNICIPIOS = pl.DataFrame(
    {
        "code": [3515004, 2400208, 2306306, 2700300, 3550308],
        "uf": ["SP", "RN", "CE", "AL", "SP"],
        "nome_norm": ["EMBU DAS ARTES", "ASSU", "ITAPAJE", "ARAPIRACA", "SAO PAULO"],
    },
    schema_overrides={"code": pl.Int32},
)


def test_match_municipios_exact_alias_fuzzy_and_miss():
    df = pl.DataFrame(
        {
            "uf": ["SP", "SP", "RN", "CE", "RN", "SP"],
            "municipio_nome": ["SÃO PAULO", "EMBU", "AÇU", "ITAPAGÉ", "MACAU", "RIO DE JANEIRO"],
        }
    )
    out = match_municipios(df, MUNICIPIOS)
    assert out.select("municipio_code", "match").rows() == [
        (3550308, "exato"),
        (3515004, "alias"),
        (2400208, "alias"),
        (2306306, "aproximado"),
        (None, None),  # MACAU isn't in this tiny reference list; must not fuzzy-match to ASSU
        (None, None),  # wrong UF: no cross-state matches
    ]


def test_author_key():
    names = pl.Series(
        [
            "Glaustin da Fokus",
            "GLAUSTIN FOKUS",
            "PAULO LEMOS (EX-PARLAMENTAR SILVIA WAIAPI NOS TERMOS ART. 78 LDO 2025)",
        ]
    )
    assert pl.select(author_key(pl.lit(names))).to_series().to_list() == ["GLAUSTIN FOKUS", "GLAUSTIN FOKUS", "PAULO LEMOS"]


def test_match_autores_prefers_legislature_then_uf():
    # Two different deputies called "Bebeto": one in legislature 55 (BA), one in 57 (RJ).
    hist = pl.DataFrame(
        {
            "deputado_id": [1, 2, 3],
            "nome": ["Bebeto", "Bebeto", "Fulano de Tal"],
            "partido": ["PSB", "PTB", "PT"],
            "uf": ["BA", "RJ", "SP"],
            "legislatura": [55, 57, 57],
        },
        schema_overrides={"deputado_id": pl.Int32, "legislatura": pl.Int32},
    )
    autores = pl.DataFrame(
        {"autor": ["BEBETO", "BEBETO", "FULANO TAL", "ALESSANDRO VIEIRA"], "ano": [2017, 2025, 2024, 2024], "uf_code": [29, 33, 35, 28]},
        schema_overrides={"ano": pl.Int32, "uf_code": pl.Int32},
    )
    out = {(r["autor"], r["ano"]): r["deputado_id"] for r in match_autores(autores, hist).iter_rows(named=True)}
    assert out[("BEBETO", 2017)] == 1  # proposed in 2016 -> legislature 55
    assert out[("BEBETO", 2025)] == 2  # proposed in 2024 -> legislature 57
    assert out[("FULANO TAL", 2024)] == 3  # particles ignored
    assert ("ALESSANDRO VIEIRA", 2024) not in out  # a senator: no match
