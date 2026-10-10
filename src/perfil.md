---
title: Perfil do deputado
---

# Perfil do deputado

Gastos da cota parlamentar, principais fornecedores e emendas de cada deputado da 57ª legislatura — três fontes ligadas pelo identificador da Câmara (CEAP) e pelo nome parlamentar (emendas).

```js
import {brl, brlCompact, MESES, num, rows} from "./components/format.js";
import {palette} from "./components/palette.js";
import {choropleth} from "./components/choropleth.js";

const deputados = rows(await FileAttachment("data/deputados.parquet").parquet());
const ceap = rows(await FileAttachment("data/ceap.parquet").parquet());
const fornecedores = rows(await FileAttachment("data/ceap-deputado-fornecedor.parquet").parquet());
const ceis = rows(await FileAttachment("data/ceap-ceis.parquet").parquet());
const emendas = rows(await FileAttachment("data/emendas.parquet").parquet());
const emendasMun = rows(await FileAttachment("data/emendas-municipios.parquet").parquet());
const municipios = rows(await FileAttachment("data/municipios.parquet").parquet());
const malhaMun = await FileAttachment("data/malha-municipios.json").json();
const pal = palette(dark);
```

```js
// Deputies in office first, then alphabetical with Portuguese collation (Á sorts with A).
const ordenados = deputados.slice().sort((a, b) => (a.em_exercicio === b.em_exercicio ? a.nome.localeCompare(b.nome, "pt-BR") : a.em_exercicio ? -1 : 1));
const doHash = deputados.find((d) => String(d.deputado_id) === location.hash.slice(1));
const deputado = view(Inputs.select(ordenados, {
  label: "Deputado(a)",
  format: (d) => `${d.nome} (${d.partido}-${d.uf})${d.em_exercicio ? "" : " — fora de exercício"}`,
  value: doHash ?? ordenados[0]
}));
```

```js
// Keep the URL shareable: /perfil#<id>
history.replaceState(null, "", `#${deputado.deputado_id}`);
const id = deputado.deputado_id;
const gastos = ceap.filter((d) => d.deputado_id === id);
const totalGasto = d3.sum(gastos, (d) => d.valor);
const ranking = d3
  .rollups(ceap.filter((d) => d.deputado_id != null), (v) => d3.sum(v, (d) => d.valor), (d) => d.deputado_id)
  .sort((a, b) => b[1] - a[1]);
const posicao = ranking.findIndex(([d]) => d === id) + 1;
const suasEmendas = emendas.filter((d) => d.deputado_id === id);
const seusCeis = ceis.filter((d) => d.deputado_id === id);
const idade = deputado.nascimento ? Math.floor((Date.now() - +deputado.nascimento) / 31_557_600_000) : null;
```

<div class="grid grid-cols-4">
  ${html`<div class="card perfil">
    <img src=${deputado.foto} alt=${`Foto de ${deputado.nome}`} width="72" height="96" loading="lazy">
    <div>
      <h2>${deputado.nome}</h2>
      <p>${deputado.partido} · ${deputado.uf}</p>
      <p class="muted small">${deputado.nome_civil ?? ""}${idade ? `, ${idade} anos` : ""}<br>${deputado.em_exercicio ? "Em exercício" : "Fora de exercício"}</p>
    </div>
  </div>`}
  <div class="card"><h2>Cota parlamentar (${d3.extent(gastos, (d) => d.ano).join("–") || "–"})</h2><span class="big">${brlCompact(totalGasto)}</span><p class="muted">${posicao ? `${posicao}º de ${ranking.length} parlamentares` : "sem despesas"}</p></div>
  <div class="card"><h2>Emendas individuais pagas</h2><span class="big">${brlCompact(d3.sum(suasEmendas, (d) => d.pago_total))}</span><p class="muted">${suasEmendas.length ? `${d3.extent(suasEmendas, (d) => d.ano).join("–")}, ${num(d3.sum(suasEmendas, (d) => d.linhas))} registros` : "nenhuma vinculada"}</p></div>
  <div class="card"><h2>Fornecedores no CEIS</h2><span class="big">${seusCeis.length}</span><p class="muted">${seusCeis.length ? brl(d3.sum(seusCeis, (d) => d.valor)) + " pagos durante a sanção" : "nenhum pagamento a empresa sancionada"}</p></div>
</div>

## Cota parlamentar

```js
const mensal = d3
  .rollups(gastos, (v) => d3.sum(v, (d) => d.valor), (d) => d.ano, (d) => d.mes)
  .flatMap(([ano, ms]) => ms.map(([mes, valor]) => ({data: new Date(Date.UTC(ano, mes - 1, 1)), ano, mes, valor})));
const porCategoria = d3.rollups(gastos, (v) => d3.sum(v, (d) => d.valor), (d) => d.categoria).map(([categoria, valor]) => ({categoria, valor}));
const mediaGeral = d3.mean(
  d3.rollups(ceap.filter((d) => d.deputado_id != null), (v) => d3.sum(v, (d) => d.valor), (d) => d.deputado_id, (d) => `${d.ano}-${d.mes}`).flatMap(([, ms]) => ms.map(([, v]) => v))
);
```

<div class="grid grid-cols-2">
  <div class="card">
    <h2>Gasto mensal</h2>
    <h3>A linha tracejada é a média de todos os deputados por mês</h3>
    ${resize((width) => Plot.plot({
      width,
      height: 300,
      marginLeft: 60,
      x: {type: "utc", label: null},
      y: {label: null, grid: true, tickFormat: brlCompact},
      marks: [
        Plot.rectY(mensal, {x: "data", interval: "month", y: "valor", fill: pal.accent, inset: 1, rx: 2}),
        Plot.ruleY([mediaGeral], {stroke: "currentColor", strokeDasharray: "4,3"}),
        Plot.ruleY([0]),
        Plot.tip(mensal, Plot.pointerX({x: "data", y: "valor", title: (d) => `${MESES[d.mes - 1]}/${d.ano}\n${brl(d.valor)}`}))
      ]
    }))}
  </div>
  <div class="card">
    <h2>Por categoria</h2>
    ${resize((width) => Plot.plot({
      width,
      height: 300,
      marginLeft: 190,
      x: {label: null, grid: true, ticks: 4, tickFormat: brlCompact},
      y: {label: null},
      marks: [
        Plot.barX(porCategoria, {y: "categoria", x: "valor", sort: {y: "-x"}, fill: pal.accent, rx: 3, tip: {format: {x: brl}}}),
        Plot.ruleX([0])
      ]
    }))}
  </div>
</div>

<div class="card">
  <h2>Principais fornecedores</h2>
  ${Inputs.table(fornecedores.filter((d) => d.deputado_id === id), {
    columns: ["fornecedor", "fornecedor_doc", "categoria", "valor", "documentos"],
    header: {fornecedor: "Fornecedor", fornecedor_doc: "CNPJ/CPF", categoria: "Categoria", valor: "Valor", documentos: "Notas"},
    format: {valor: brl, documentos: num},
    rows: 10
  })}
</div>

${seusCeis.length ? html`<div class="warning"><p><strong>Pagamentos a fornecedores com sanção vigente no CEIS:</strong></p><ul>${seusCeis.map((d) => html`<li>${d.fornecedor} — ${brl(d.valor)} (${d.categoria}); sanção: ${d.sancao}, ${d.orgao}, abrangência: ${d.abrangencia}</li>`)}</ul><p class="small">Muitas sanções valem só para o órgão que as aplicou; isto não indica irregularidade por si só.</p></div>` : ""}

## Emendas

```js
const porAno = d3.rollups(suasEmendas, (v) => d3.sum(v, (d) => d.pago_total), (d) => d.ano).map(([ano, valor]) => ({ano, valor}));
const porFuncao = d3.rollups(suasEmendas, (v) => d3.sum(v, (d) => d.pago_total), (d) => d.funcao).map(([funcao, valor]) => ({funcao, valor})).filter((d) => d.valor > 0);
const recebido = d3.rollup(emendasMun.filter((d) => d.deputado_id === id), (v) => d3.sum(v, (d) => d.valor), (d) => d.municipio_code);
const munByCode = new Map(municipios.map((d) => [d.code, d]));
const featMun = topojson.feature(malhaMun, malhaMun.objects.BRMU).features;
// Zoom on the deputy's state plus anywhere else their emendas reached.
const recorte = featMun.filter((f) => munByCode.get(+f.properties.codarea)?.uf === deputado.uf || recebido.has(+f.properties.codarea));
```

${suasEmendas.length === 0 ? html`<p class="note">Nenhuma emenda individual vinculada a este nome parlamentar. Os autores são ligados aos deputados pelo nome (ver <a href="./sobre">metodologia</a>); suplentes com poucos meses de mandato costumam não ter emendas.</p>` : ""}

<div class="grid grid-cols-2">
  <div class="card">
    <h2>Valor pago por ano da emenda</h2>
    ${resize((width) => Plot.plot({
      width,
      height: 260,
      marginLeft: 60,
      x: {label: null, tickFormat: "d", type: "band"},
      y: {label: null, grid: true, tickFormat: brlCompact},
      marks: [Plot.barY(porAno, {x: "ano", y: "valor", fill: pal.accent, rx: 3, tip: {format: {y: brl}}}), Plot.ruleY([0])]
    }))}
  </div>
  <div class="card">
    <h2>Por função de governo</h2>
    ${resize((width) => Plot.plot({
      width,
      height: 260,
      marginLeft: 150,
      x: {label: null, grid: true, ticks: 3, tickFormat: brlCompact},
      y: {label: null},
      marks: [Plot.barX(porFuncao, {y: "funcao", x: "valor", sort: {y: "-x", limit: 10}, fill: pal.accent, rx: 3, tip: {format: {x: brl}}}), Plot.ruleX([0])]
    }))}
  </div>
</div>

<div class="card">
  <h2>Onde o dinheiro chegou</h2>
  <h3>Valores recebidos por favorecidos localizados em cada município (todas as emendas individuais do autor)</h3>
  ${recebido.size ? resize((width) => choropleth(recorte, recebido, {
    width,
    color: {type: "quantile", n: 5, range: pal.blues(5), tickFormat: brlCompact},
    label: "Recebido",
    format: brl,
    noData: pal.noData,
    title: (code) => `${munByCode.get(code)?.nome} (${munByCode.get(code)?.uf})`
  })) : html`<p class="muted">Sem pagamentos a favorecidos identificados.</p>`}
</div>

<style>
.perfil { display: flex; gap: 1rem; align-items: flex-start; }
.perfil img { border-radius: 6px; object-fit: cover; flex-shrink: 0; }
.perfil h2 { margin: 0 0 .25rem; }
.perfil p { margin: 0 0 .25rem; }
.small { font-size: .85rem; }
</style>
