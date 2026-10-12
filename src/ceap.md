---
title: Cota parlamentar (Câmara)
---

# Cota parlamentar (CEAP)

A Cota para o Exercício da Atividade Parlamentar reembolsa despesas como passagens, combustível, divulgação e escritório. Fonte: arquivos anuais em massa da Câmara (um CSV por ano, com cada nota fiscal), limpos e agregados por deputado, mês e categoria.

```js
import {brl, brlCompact, MESES, num, numCompact, resultados, rows} from "./components/format.js";
import {palette} from "./components/palette.js";
import {eleicoesMarks, hbars, labelMargin, picoMark} from "./components/charts.js";
import {grupoPartido, partyScale} from "./components/parties.js";

const ceap = rows(await FileAttachment("data/ceap.parquet").parquet());
const fornecedores = rows(await FileAttachment("data/ceap-fornecedores.parquet").parquet());
const ceis = rows(await FileAttachment("data/ceap-ceis.parquet").parquet());
const pal = palette(dark);
```

```js
const anos = [...new Set(ceap.map((d) => d.ano))].sort();
const partidos = [...new Set(ceap.filter((d) => !d.lideranca).map((d) => d.partido))].filter(Boolean).sort();
const ufs = [...new Set(ceap.map((d) => d.uf))].filter(Boolean).sort();

const filtros = view(Inputs.form({
  ano: Inputs.select(["Todos", ...anos], {label: "Ano", value: "Todos"}),
  partido: Inputs.select(["Todos", ...partidos], {label: "Partido", value: "Todos"}),
  uf: Inputs.select(["Todas", ...ufs], {label: "UF", value: "Todas"}),
  liderancas: Inputs.toggle({label: "Incluir lideranças", value: false})
}));
```

```js
const dados = ceap.filter((d) =>
  (filtros.ano === "Todos" || d.ano === filtros.ano) &&
  (filtros.partido === "Todos" || d.partido === filtros.partido) &&
  (filtros.uf === "Todas" || d.uf === filtros.uf) &&
  (filtros.liderancas || !d.lideranca)
);
const total = d3.sum(dados, (d) => d.valor);
const nDeputados = new Set(dados.map((d) => d.deputado_id).filter((d) => d != null)).size;
// Average per deputy-month: months in which the deputy had any expense.
const deputadoMeses = new Set(dados.filter((d) => d.deputado_id != null).map((d) => `${d.deputado_id}-${d.ano}-${d.mes}`)).size;
```

<div class="grid grid-cols-4">
  <div class="card"><h2>Total reembolsado</h2><span class="big">${brlCompact(total)}</span></div>
  <div class="card"><h2>Parlamentares</h2><span class="big">${num(nDeputados)}</span></div>
  <div class="card"><h2>Notas fiscais</h2><span class="big">${numCompact(d3.sum(dados, (d) => d.documentos))}</span></div>
  <div class="card"><h2>Média por deputado e mês</h2><span class="big">${brlCompact(total / deputadoMeses)}</span></div>
</div>

```js
const mensal = d3
  .rollups(dados, (v) => d3.sum(v, (d) => d.valor), (d) => d.ano, (d) => d.mes)
  .flatMap(([ano, meses]) => meses.map(([mes, valor]) => ({data: new Date(Date.UTC(ano, mes - 1, 1)), ano, mes, valor})));
const ultimoMes = d3.max(mensal, (d) => d.data);
```

<div class="card">
  <h2>Gasto mensal</h2>
  <h3>Pelo mês de competência da despesa. Os meses mais recentes ainda recebem notas (há atraso de até 90 dias para apresentação).</h3>
  ${resize((width) => Plot.plot({
    width,
    height: 280,
    marginLeft: 60,
    x: {type: "utc", label: null},
    y: {label: null, grid: true, tickFormat: brlCompact, insetTop: 22},
    marks: [
      Plot.rectY(mensal, {x: "data", interval: "month", y: "valor", fill: (d) => (+d.data > +d3.utcMonth.offset(ultimoMes, -3) ? pal.muted : pal.accent), inset: 1, ry1: 2}),
      Plot.ruleY([0]),
      ...eleicoesMarks(d3.extent(mensal, (d) => d.data), {width}),
      picoMark(mensal, (d) => `Pico: ${MESES[d.mes - 1]}/${d.ano}, ${brlCompact(d.valor)}`),
      Plot.tip(mensal, Plot.pointerX({x: "data", y: "valor", title: (d) => `${MESES[d.mes - 1]}/${d.ano}\n${brl(d.valor)}`}))
    ]
  }))}
  <p class="muted">Em cinza, os meses mais recentes — ainda incompletos. As linhas verticais marcam o primeiro turno das eleições.</p>
</div>

```js
const porCategoria = d3.rollups(dados, (v) => d3.sum(v, (d) => d.valor), (d) => d.categoria).map(([categoria, valor]) => ({categoria, valor}));
const porDeputado = d3
  .rollups(dados.filter((d) => d.deputado_id != null), (v) => ({valor: d3.sum(v, (d) => d.valor), nome: v[0].nome, partido: v.at(-1).partido, uf: v.at(-1).uf}), (d) => d.deputado_id)
  .map(([id, d]) => ({id, ...d}))
  .sort((a, b) => b.valor - a.valor);
```

<div class="grid grid-cols-2">
  <div class="card">
    <h2>Por categoria</h2>
    ${resize((width) => hbars(porCategoria, {width, y: "categoria", fill: pal.accent}))}
  </div>
  <div class="card">
    <h2>Maiores gastos individuais</h2>
    <h3>Os 20 parlamentares com mais reembolsos no recorte, na cor do partido</h3>
    ${resize((width) => hbars(porDeputado, {
      width,
      limit: 20,
      y: (d) => `${d.nome} (${d.partido}-${d.uf})`,
      fill: (d) => grupoPartido(d.partido),
      color: partyScale(pal, {legend: true}),
      href: (d) => `./perfil#${d.id}`,
      maxMargin: 190
    }))}
    <p class="muted">Clique numa barra para abrir o perfil. Deputados com mandato mais longo no período naturalmente acumulam mais.</p>
  </div>
</div>

```js
// Spending per deputy-month by party, so that big and small benches compare fairly.
const porPartido = d3
  .rollups(dados.filter((d) => d.deputado_id != null && d.partido), (v) => ({
    valor: d3.sum(v, (d) => d.valor),
    deputados: new Set(v.map((d) => d.deputado_id)).size,
    meses: new Set(v.map((d) => `${d.deputado_id}-${d.ano}-${d.mes}`)).size
  }), (d) => d.partido)
  .map(([partido, d]) => ({partido, ...d, media: d.valor / d.meses}))
  .filter((d) => d.deputados >= 5);
```

<div class="card">
  <h2>Gasto médio por deputado e mês, por partido</h2>
  <h3>Partidos com pelo menos 5 deputados no recorte; a linha tracejada marca a média geral</h3>
  ${resize((width) => Plot.plot({
    width,
    height: Math.max(220, porPartido.length * 26 + 50),
    marginLeft: Math.min(110, labelMargin(width, 110)),
    marginRight: 24,
    marginTop: 28,
    x: {label: "por deputado-mês", grid: true, tickFormat: brlCompact, ticks: width < 500 ? 3 : 6},
    y: {label: null, tickSize: 0},
    color: partyScale(pal, {legend: true}),
    marks: [
      Plot.ruleY(porPartido, {y: "partido", x1: 0, x2: "media", stroke: "currentColor", strokeOpacity: 0.25, strokeWidth: 2, sort: {y: "-x2"}}),
      Plot.ruleX([total / deputadoMeses], {stroke: "currentColor", strokeOpacity: 0.7, strokeDasharray: "4,3"}),
      Plot.text([total / deputadoMeses], {x: (d) => d, frameAnchor: "top", dy: -18, textAnchor: "middle", text: (d) => `média geral: ${brlCompact(d)}`, fill: "currentColor", fontSize: 11}),
      Plot.dot(porPartido, {y: "partido", x: "media", r: 6, fill: (d) => grupoPartido(d.partido), stroke: "var(--theme-background-alt)", strokeWidth: 2, channels: {deputados: "deputados"}, tip: {format: {x: brl, fill: false}}})
    ]
  }))}
</div>

## Fornecedores

Os ${num(fornecedores.length)} maiores fornecedores no período inteiro, identificados pelo CNPJ/CPF (o nome exibido é o mais frequente nas notas).

```js
const buscaForn = view(Inputs.search(fornecedores, {placeholder: "Buscar fornecedor, CNPJ ou categoria…", format: resultados}));
```

```js
Inputs.table(buscaForn, {
  columns: ["fornecedor", "fornecedor_doc", "categoria_principal", "valor", "documentos", "deputados"],
  header: {fornecedor: "Fornecedor", fornecedor_doc: "CNPJ/CPF", categoria_principal: "Categoria principal", valor: "Valor", documentos: "Notas", deputados: "Deputados"},
  format: {valor: brl, documentos: num, deputados: num},
  width: {fornecedor: 280},
  rows: 12
})
```

## Fornecedores com sanção vigente (CEIS)

```js
const ceisTotal = d3.sum(ceis, (d) => d.valor);
```

Cruzamos o CNPJ/CPF de cada nota com o **Cadastro de Empresas Inidôneas e Suspensas** (Portal da Transparência, snapshot de ${ceis[0] ? new Date(ceis[0].ceis_snapshot + "T12:00").toLocaleDateString("pt-BR") : "–"}), considerando só despesas com data de emissão **dentro** do período da sanção: ${num(ceis.length)} combinações deputado–fornecedor, ${brlCompact(ceisTotal)} no total.

<div class="warning">Muitas sanções do CEIS valem apenas para o órgão que as aplicou (veja a coluna “Abrangência”) e não proíbem contratos com a Câmara. Um registro aqui é um ponto de partida para checagem, não indício de irregularidade.</div>

```js
Inputs.table(ceis, {
  columns: ["nome", "partido", "uf", "fornecedor", "categoria", "sancao", "abrangencia", "orgao", "valor", "documentos"],
  header: {nome: "Parlamentar", partido: "Partido", uf: "UF", fornecedor: "Fornecedor", categoria: "Despesa", sancao: "Sanção", abrangencia: "Abrangência", orgao: "Órgão sancionador", valor: "Valor", documentos: "Notas"},
  format: {valor: brl},
  width: {fornecedor: 200, orgao: 220, sancao: 200},
  rows: 10
})
```
