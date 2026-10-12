"""CEAP expenses paid to suppliers listed in CEIS on the expense date.

CEIS (Cadastro de Empresas Inidôneas e Suspensas) lists companies and people
barred from contracting with some or all of the public administration. Many
sanctions are limited in scope (one agency or one state), so a match here is a
starting point for scrutiny, not evidence of wrongdoing.
"""

import duckdb
import polars as pl

from pipeline import frames
from pipeline.clean import doc_publico_expr
from pipeline.io import emit_parquet

ceap = frames.ceap()
ceis = frames.ceis()
df = duckdb.sql(
    """
    SELECT c.deputado_id, any_value(c.nome) AS nome, any_value(c.partido) AS partido, any_value(c.uf) AS uf,
           c.fornecedor_doc, mode(c.fornecedor) AS fornecedor, mode(c.categoria) AS categoria,
           s.categoria AS sancao, s.orgao, s.abrangencia, s.inicio, s.fim,
           round(sum(c.valor), 2) AS valor, count(*) AS documentos,
           min(c.data_emissao) AS primeira, max(c.data_emissao) AS ultima,
           any_value(s.snapshot) AS ceis_snapshot
    FROM ceap c
    JOIN ceis s
      ON c.fornecedor_doc = s.doc
     AND c.data_emissao >= s.inicio
     AND (s.fim IS NULL OR c.data_emissao <= s.fim)
    GROUP BY c.deputado_id, c.fornecedor_doc, s.categoria, s.orgao, s.abrangencia, s.inicio, s.fim
    ORDER BY valor DESC
    """
).pl()
# Mask CPFs (people) after the joins/grouping, which need the full digits.
emit_parquet(df.with_columns(doc_publico_expr(pl.col("fornecedor_doc")).alias("fornecedor_doc")))
