---
title: Emendas parlamentares
---

# Emendas parlamentares

Emendas são a parte do Orçamento da União que deputados e senadores direcionam a projetos e localidades. Fonte: download em massa do Portal da Transparência (sem chave de API), com autores ligados aos deputados da Câmara e municípios ligados aos códigos do IBGE.

```js
import {brl, brlCompact, num, pct, resultados, rows} from "./components/format.js";
import {palette} from "./components/palette.js";
import {choropleth} from "./components/choropleth.js";
import {treemap} from "./components/treemap.js";
import {hbars} from "./components/charts.js";
import {grupoPartido, OUTROS, partyColor} from "./components/parties.js";

const emendas = rows(await FileAttachment("data/emendas.parquet").parquet());
const emendasMun = rows(await FileAttachment("data/emendas-municipios.parquet").parquet());
const municipios = rows(await FileAttachment("data/municipios.parquet").parquet());
const malhaMun = await FileAttachment("data/malha-municipios.json").json();
const malhaUf = await FileAttachment("data/malha-uf.json").json();
const pal = palette(dark);
```

```js
const anos = [...new Set(emendas.map((d) => d.ano))].sort();
const TIPOS = ["Individual", "Bancada", "Comissão", "Relator"];
const filtros = view(Inputs.form({
  de: Inputs.select(anos, {label: "De", value: Math.max(anos[0], 2019), format: String}),
  ate: Inputs.select(anos, {label: "Até", value: anos.at(-1), format: String}),
  tipos: Inputs.checkbox(TIPOS, {label: "Tipo", value: TIPOS})
}));
```

```js
const noPeriodo = (d) => d.ano >= filtros.de && d.ano <= filtros.ate && filtros.tipos.includes(d.tipo_grupo);
const dados = emendas.filter(noPeriodo);
const pago = d3.sum(dados, (d) => d.pago_total);
const empenhado = d3.sum(dados, (d) => d.empenhado);
const anoAtual = anos.at(-1);
```

<div class="grid grid-cols-4">
  <div class="card"><h2>Pago</h2><span class="big">${brlCompact(pago)}</span><p class="muted">no ano da emenda + restos a pagar</p></div>
  <div class="card"><h2>Empenhado</h2><span class="big">${brlCompact(empenhado)}</span><p class="muted">valor reservado no orçamento</p></div>
  <div class="card"><h2>Execução</h2><span class="big">${pct(pago / empenhado)}</span><p class="muted">pago ÷ empenhado${filtros.ate === anoAtual ? ` (${anoAtual} ainda em execução)` : ""}</p></div>
  <div class="card"><h2>Por deputados</h2><span class="big">${pct(d3.sum(dados.filter((d) => d.autor_tipo === "Deputado(a)"), (d) => d.pago_total) / pago)}</span><p class="muted">do valor pago tem autor ligado a um deputado</p></div>
</div>

```js
const porAnoTipo = d3
  .rollups(dados, (v) => d3.sum(v, (d) => d.pago_total), (d) => d.ano, (d) => d.tipo_grupo)
  .flatMap(([ano, tipos]) => tipos.map(([tipo, valor]) => ({ano, tipo, valor})));
const totalAno = d3.rollup(porAnoTipo, (v) => d3.sum(v, (d) => d.valor), (d) => d.ano);
const valorDe = (ano, tipo) => d3.sum(porAnoTipo.filter((d) => d.ano === ano && d.tipo === tipo), (d) => d.valor);
// Annotations only for years and types inside the current filter.
const notas = [
  filtros.tipos.includes("Relator") && totalAno.has(2020) && {
    ano: 2020,
    texto: `Emendas de relator (RP9), o “orçamento secreto”: ${brlCompact(valorDe(2020, "Relator"))} em 2020`
  },
  totalAno.has(2023) && {
    ano: 2023,
    texto: `Após o STF derrubar o RP9 (dez/2022), individuais e de comissão crescem`
  }
].filter(Boolean).map((d) => ({...d, valor: totalAno.get(d.ano)}));
```

<div class="card">
  <h2>Valor pago por ano e tipo de emenda</h2>
  <h3>As emendas de relator-geral (RP9, o “orçamento secreto”) foram a maior fatia em 2020–2021; o STF as declarou inconstitucionais em dezembro de 2022</h3>
  ${resize((width) => Plot.plot({
    width,
    height: 340,
    marginLeft: 60,
    x: {label: null, tickFormat: "d", type: "band"},
    y: {label: null, grid: true, tickFormat: brlCompact, insetTop: notas.length ? 70 : 0},
    color: {legend: true, domain: TIPOS, range: pal.categorical.slice(0, 4)},
    marks: [
      Plot.barY(porAnoTipo, {x: "ano", y: "valor", fill: "tipo", order: TIPOS, stroke: "var(--theme-background-alt)", strokeWidth: 1.5, tip: {format: {y: brl}}}),
      Plot.ruleY([0]),
      Plot.tip(notas, {x: "ano", y: "valor", title: "texto", anchor: "bottom", lineWidth: width < 600 ? 14 : 22, fontSize: 11, pointerEvents: "none"})
    ]
  }))}
</div>

## Onde o dinheiro chegou

```js
const pop = new Map(municipios.map((d) => [d.code, d.pop_est]));
const munByCode = new Map(municipios.map((d) => [d.code, d]));
const recebido = d3.rollup(emendasMun.filter(noPeriodo), (v) => d3.sum(v, (d) => d.valor), (d) => d.municipio_code);
const perCapita = new Map([...recebido].filter(([c]) => pop.get(c) > 0).map(([c, v]) => [c, v / pop.get(c)]));
const featMun = topojson.feature(malhaMun, malhaMun.objects.BRMU).features;
const featUf = topojson.feature(malhaUf, malhaUf.objects.BRUF).features;
const nAnos = filtros.ate - filtros.de + 1;
const ufs = [...new Set(municipios.map((d) => d.uf))].sort();
```

```js
const ufInput = Inputs.select(["Brasil", ...ufs], {label: "Mapa", value: "Brasil"});
const ufMapa = view(ufInput);
```

```js
// Clicking a municipality on the national map zooms into its state.
function ampliar(code) {
  if (ufInput.value !== "Brasil") return;
  ufInput.value = munByCode.get(code)?.uf ?? "Brasil";
  ufInput.dispatchEvent(new Event("input", {bubbles: true}));
}
const featMapa = ufMapa === "Brasil" ? featMun : featMun.filter((f) => munByCode.get(+f.properties.codarea)?.uf === ufMapa);
const ufCode = municipios.find((d) => d.uf === ufMapa)?.uf_code;
const bordasMapa = ufMapa === "Brasil" ? featUf : featUf.filter((f) => +f.properties.codarea === ufCode);
```

<div class="card">
  <h2>Recebido por habitante, ${filtros.de}–${filtros.ate} — ${ufMapa}</h2>
  <h3>Pagamentos a favorecidos sediados em cada município ÷ população estimada; faixas com o mesmo número de municípios${ufMapa === "Brasil" ? ". Clique num município para ampliar o estado" : ""}</h3>
  ${resize((width) => choropleth(featMapa, perCapita, {
    width,
    color: {type: "quantile", n: 7, range: pal.blues(7), tickFormat: (d) => brl(d)},
    label: "R$ por habitante",
    format: (v) => `${brl(v)} por habitante (${brl(v / nAnos)}/ano)`,
    noData: pal.noData,
    borders: bordasMapa,
    onSelect: ufMapa === "Brasil" ? ampliar : null,
    title: (code) => `${munByCode.get(code)?.nome} (${munByCode.get(code)?.uf})`
  }))}
  <p class="muted">O município é o do <em>favorecido</em> (prefeitura, empresa, ONG) que recebeu o pagamento — o arquivo traz só nome e UF, ligados ao código IBGE por nome normalizado, tabela de renomeações e correspondência aproximada. Capitais concentram favorecidos estaduais e federais, o que infla seus valores.</p>
</div>

## Quem envia

```js
const individuais = dados.filter((d) => d.autor_tipo === "Deputado(a)");
const porDeputado = d3
  .rollups(individuais, (v) => ({valor: d3.sum(v, (d) => d.pago_total), partido: v.at(-1).deputado_partido, uf: v.at(-1).deputado_uf, nome: v[0].deputado_nome}), (d) => d.deputado_id)
  .map(([id, d]) => ({id, ...d}));
```

<div class="card">
  <h2>Emendas individuais de deputados, por partido e deputado</h2>
  <h3>Área proporcional ao valor pago no período; as sete maiores bancadas têm cor própria, as demais aparecem em “Outros”. Passe o mouse para detalhes.</h3>
  ${resize((width) => treemap(porDeputado.map((d) => ({group: grupoPartido(d.partido), item: `${d.nome} (${d.partido ?? "s/ partido"}-${d.uf})`, value: d.valor})), {width, height: 520, color: (g) => partyColor(pal, g), format: brlCompact}))}
  <p class="muted">Partido do deputado na legislatura da emenda (última filiação registrada pela Câmara naquela legislatura). Treemap desenhado com D3 — o Plot não tem layouts hierárquicos.</p>
</div>

```js
const porFuncao = d3.rollups(dados, (v) => d3.sum(v, (d) => d.pago_total), (d) => d.funcao).map(([funcao, valor]) => ({funcao, valor}));
const porAutorTipo = d3.rollups(dados, (v) => d3.sum(v, (d) => d.pago_total), (d) => d.autor_tipo).map(([autor_tipo, valor]) => ({autor_tipo, valor}));
```

<div class="grid grid-cols-2">
  <div class="card">
    <h2>Por função de governo</h2>
    ${resize((width) => hbars(porFuncao, {width, y: "funcao", fill: pal.accent, limit: 15, maxMargin: 160}))}
  </div>
  <div class="card">
    <h2>Por tipo de autor</h2>
    ${resize((width) => hbars(porAutorTipo, {width, y: "autor_tipo", fill: pal.accent, maxMargin: 120}))}
    <p class="muted">Autores individuais que não correspondem a nenhum deputado das legislaturas 55–57 são, na prática, senadores.</p>
  </div>
</div>

```js
const busca = view(Inputs.search(porDeputado, {placeholder: "Buscar deputado, partido ou UF…", format: resultados}));
```

```js
Inputs.table(busca, {
  columns: ["nome", "partido", "uf", "valor"],
  header: {nome: "Deputado(a)", partido: "Partido", uf: "UF", valor: "Pago no período"},
  format: {nome: (n, i, data) => html`<a href="./perfil#${data[i].id}">${n}</a>`, valor: brl},
  sort: "valor",
  reverse: true,
  rows: 12
})
```
