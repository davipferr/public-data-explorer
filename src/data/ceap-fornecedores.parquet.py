"""CEAP suppliers (by CNPJ/CPF): totals and how many deputies paid them.

Supplier names vary between documents ("POSTO X LTDA", "Posto X"), so the name
shown is the most frequent one for each document number.
"""

import duckdb

from pipeline import frames
from pipeline.io import emit_parquet

ceap = frames.ceap()
df = duckdb.sql(
    """
    SELECT fornecedor_doc,
           mode(fornecedor)            AS fornecedor,
           any_value(fornecedor_tipo)  AS tipo,
           mode(categoria)             AS categoria_principal,
           round(sum(valor), 2)        AS valor,
           count(*)                    AS documentos,
           count(DISTINCT deputado_id) AS deputados,
           min(ano)                    AS primeiro_ano,
           max(ano)                    AS ultimo_ano
    FROM ceap
    WHERE fornecedor_doc IS NOT NULL
    GROUP BY fornecedor_doc
    HAVING sum(valor) > 0
    ORDER BY valor DESC
    LIMIT 5000
    """
).pl()
emit_parquet(df)
