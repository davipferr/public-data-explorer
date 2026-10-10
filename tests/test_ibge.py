import json

import pipeline.ibge as ibge

PAYLOAD = [
    {
        "id": "93",
        "variavel": "População residente",
        "unidade": "Pessoas",
        "resultados": [
            {
                "classificacoes": [],
                "series": [
                    {"localidade": {"id": "11", "nivel": {"id": "N3", "nome": "UF"}, "nome": "Rondônia"}, "serie": {"2021": "1815278", "2022": "1581196"}},
                    {"localidade": {"id": "12", "nivel": {"id": "N3", "nome": "UF"}, "nome": "Acre"}, "serie": {"2021": "-", "2022": "X"}},
                ],
            }
        ],
    }
]


def test_sidra_flattens_nested_json_and_maps_special_symbols(monkeypatch):
    calls = {}

    def fake_fetch(url, params=None, **kwargs):
        calls["url"], calls["params"] = url, params
        return json.dumps(PAYLOAD).encode()

    monkeypatch.setattr(ibge, "fetch", fake_fetch)
    df = ibge.sidra(4709, 93, "2021|2022", nivel="N3")

    assert calls["url"].endswith("/agregados/4709/periodos/2021|2022/variaveis/93")
    assert calls["params"] == {"localidades": "N3[all]"}
    assert df.height == 4
    rows = {(r["localidade_id"], r["ano"]): r["valor"] for r in df.iter_rows(named=True)}
    assert rows[(11, 2022)] == 1581196.0
    assert rows[(12, 2021)] == 0.0  # "-" is a true zero
    assert rows[(12, 2022)] is None  # "X" is suppressed


def test_municipios_handles_missing_microrregiao(monkeypatch):
    data = [
        {"id": 3550308, "nome": "São Paulo", "microrregiao": {"mesorregiao": {"UF": {"id": 35}}}},
        {
            "id": 5101837,
            "nome": "Boa Esperança do Norte",
            "microrregiao": None,
            "regiao-imediata": {"regiao-intermediaria": {"UF": {"id": 51}}},
        },
    ]
    monkeypatch.setattr(ibge, "fetch", lambda *a, **k: json.dumps(data).encode())
    df = ibge.municipios()
    assert df.select("code", "uf", "nome_norm").rows() == [
        (3550308, "SP", "SAO PAULO"),
        (5101837, "MT", "BOA ESPERANCA DO NORTE"),
    ]
