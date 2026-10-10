"""Build metadata and data-quality report: how well the cross-source joins worked."""

import json
from datetime import datetime, timezone

import polars as pl

from pipeline import frames, ibge, portal
from pipeline.io import emit_json


def share(df: pl.DataFrame, by: str, value: str) -> list[dict]:
    total = df[value].sum()
    return (
        df.group_by(pl.col(by).fill_null("sem correspondência"))
        .agg(pl.len().alias("linhas"), pl.col(value).sum().alias("valor"))
        .with_columns((pl.col("valor") / total).alias("parcela"))
        .sort("valor", descending=True)
        .to_dicts()
    )


mun = frames.municipios()
mesh = json.loads(ibge.malha("municipio"))
mesh_codes = {int(g["properties"]["codarea"]) for g in next(iter(mesh["objects"].values()))["geometries"]}
fora_da_malha = mun.filter(~pl.col("code").is_in(list(mesh_codes))).select("code", "nome", "uf").to_dicts()

fav = frames.emendas_favorecidos()
em = frames.emendas()
ind = em.filter(pl.col("tipo_grupo") == "Individual", pl.col("autor").is_not_null())
ceap = frames.ceap()
ceis = frames.ceis()

fuzzy = (
    fav.filter(pl.col("match").is_in(["alias", "aproximado"]))
    .select("uf", "municipio_nome", "municipio_code", "match")
    .unique()
    .join(mun.select(pl.col("code").alias("municipio_code"), pl.col("nome").alias("nome_ibge")), on="municipio_code")
    .sort("uf", "municipio_nome")
    .to_dicts()
)

report = {
    "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "municipios": {"oficiais": mun.height, "na_malha": len(mesh_codes), "fora_da_malha": fora_da_malha},
    "ceap": {
        "documentos": ceap.height,
        "anos": sorted(ceap["ano"].unique().to_list()),
        "liderancas_documentos": int(ceap["lideranca"].sum()),
        "valor_total": ceap["valor"].sum(),
    },
    "emendas": {
        "linhas": em.height,
        "anos": sorted(em["ano"].unique().to_list()),
        "por_escopo": share(em, "escopo", "pago_total"),
        "autores_individuais": ind["autor"].n_unique(),
        "autores_vinculados_a_deputados": ind.filter(pl.col("deputado_id").is_not_null())["autor"].n_unique(),
    },
    "favorecidos": {
        "linhas": fav.height,
        "correspondencia_municipio": share(fav, "match", "valor"),
        "nomes_corrigidos": fuzzy,
    },
    "ceis": {"snapshot": ceis["snapshot"][0], "sancoes": ceis.height},
    "portal_api": {"chave_configurada": portal.api_key() is not None},
}
emit_json(json.loads(json.dumps(report, default=str)))
