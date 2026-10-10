---
title: Consulta SQL
---

# Consulta SQL no navegador

Os arquivos Parquet que alimentam o site são carregados num **DuckDB rodando no seu navegador** (DuckDB-WASM). Nada é enviado a servidor algum — faça as suas próprias comparações.

```js
const db = DuckDBClient.of({
  municipios: FileAttachment("data/municipios.parquet"),
  deputados: FileAttachment("data/deputados.parquet"),
  ceap: FileAttachment("data/ceap.parquet"),
  fornecedores: FileAttachment("data/ceap-fornecedores.parquet"),
  ceap_ceis: FileAttachment("data/ceap-ceis.parquet"),
  emendas: FileAttachment("data/emendas.parquet"),
  emendas_municipios: FileAttachment("data/emendas-municipios.parquet")
});
```

```js
const exemplos = new Map([
  ["Emendas por habitante, por UF (2023 em diante)", `WITH recebido AS (
  SELECT municipio_code, sum(valor) AS valor
  FROM emendas_municipios
  WHERE ano >= 2023
  GROUP BY 1
)
SELECT m.uf,
       round(sum(coalesce(r.valor, 0)) / sum(m.pop_est), 2) AS reais_por_habitante
FROM municipios m
LEFT JOIN recebido r ON r.municipio_code = m.code
GROUP BY m.uf
ORDER BY reais_por_habitante DESC`],
  ["Quanto cada partido gastou de cota, por deputado", `SELECT partido,
       count(DISTINCT deputado_id)                        AS deputados,
       round(sum(valor) / count(DISTINCT deputado_id), 0) AS media_por_deputado
FROM ceap
WHERE NOT lideranca
GROUP BY partido
HAVING deputados >= 5
ORDER BY media_por_deputado DESC`],
  ["Deputados que mais gastaram com divulgação", `SELECT nome, partido, uf, round(sum(valor), 0) AS divulgacao
FROM ceap
WHERE categoria = 'Divulgação da atividade'
GROUP BY ALL
ORDER BY divulgacao DESC
LIMIT 20`],
  ["Cota × emendas: os mesmos deputados lideram?", `WITH c AS (
  SELECT deputado_id, sum(valor) AS cota FROM ceap WHERE deputado_id IS NOT NULL GROUP BY 1
), e AS (
  SELECT deputado_id, sum(pago_total) AS emendas FROM emendas
  WHERE deputado_id IS NOT NULL AND ano >= 2023 GROUP BY 1
)
SELECT d.nome, d.partido, d.uf, round(c.cota) AS cota, round(e.emendas) AS emendas
FROM deputados d JOIN c USING (deputado_id) LEFT JOIN e USING (deputado_id)
ORDER BY cota DESC
LIMIT 25`],
  ["Municípios mais ricos por PIB per capita", `SELECT nome, uf, pop_est, round(pib_pc) AS pib_per_capita
FROM municipios
ORDER BY pib_pc DESC NULLS LAST
LIMIT 20`]
]);
const exemplo = view(Inputs.select(exemplos, {label: "Exemplo"}));
```

```js
const consulta = view(Inputs.textarea({value: exemplo, rows: 10, submit: "Executar", spellcheck: false, monospace: true, width: "100%"}));
```

```js
// DuckDB returns BIGINT/HUGEINT (e.g. count(*)) as JavaScript BigInt; convert to
// Number so formatting and charts work.
const resultado = await db.query(consulta).then(
  (r) => ({rows: Array.from(r, (row) => Object.fromEntries(Object.entries(row).map(([k, v]) => [k, typeof v === "bigint" ? Number(v) : v])))}),
  (error) => ({error})
);
```

${resultado.error ? html`<div class="caution"><strong>Erro:</strong> <code>${resultado.error.message}</code></div>` : html`<p class="muted">${resultado.rows.length.toLocaleString("pt-BR")} linhas</p>`}

```js
resultado.error ? null : Inputs.table(resultado.rows, {rows: 20, locale: "pt-BR"})
```

## Tabelas disponíveis

```js
const esquema = await Promise.all(
  ["municipios", "deputados", "ceap", "fornecedores", "ceap_ceis", "emendas", "emendas_municipios"].map(async (t) => ({
    tabela: t,
    linhas: Number(Array.from(await db.query(`SELECT count(*) AS n FROM ${t}`))[0].n),
    colunas: Array.from(await db.query(`DESCRIBE ${t}`), (c) => `${c.column_name} (${c.column_type.toLowerCase()})`).join(", ")
  }))
);
```

```js
Inputs.table(esquema, {format: {linhas: (n) => n.toLocaleString("pt-BR")}, width: {tabela: 150, linhas: 90}, layout: "auto"})
```

<div class="tip">Valores em reais estão em <code>valor</code>, <code>pago_total</code>, <code>empenhado</code>, <code>pib</code> e <code>pib_pc</code>. Códigos de município são os de 7 dígitos do IBGE (<code>code</code>, <code>municipio_code</code>); <code>deputado_id</code> é o identificador da Câmara.</div>
