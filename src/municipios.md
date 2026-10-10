---
title: Municípios (IBGE)
---

# Municípios

População e economia dos ${municipios.length.toLocaleString("pt-BR")} municípios brasileiros, a partir da API SIDRA (tabelas 4709, 6579 e 5938) e da malha territorial do IBGE.

```js
import {brlCompact, num, numCompact, pct, rows} from "./components/format.js";
import {palette} from "./components/palette.js";
import {choropleth} from "./components/choropleth.js";

const municipios = rows(await FileAttachment("data/municipios.parquet").parquet());
const popUf = rows(await FileAttachment("data/populacao-uf.parquet").parquet());
const malhaMun = await FileAttachment("data/malha-municipios.json").json();
const malhaUf = await FileAttachment("data/malha-uf.json").json();
const qualidade = await FileAttachment("data/qualidade.json").json();
```

```js
const featMun = topojson.feature(malhaMun, malhaMun.objects.BRMU).features;
const featUf = topojson.feature(malhaUf, malhaUf.objects.BRUF).features;
const byCode = new Map(municipios.map((d) => [d.code, d]));
const ufs = [...new Set(municipios.map((d) => d.uf))].sort();
const pal = palette(dark);
const popAno = municipios[0].pop_est_ano;
const pibAno = municipios[0].pib_ano;
```

```js
const metricas = new Map([
  [`População estimada (${popAno})`, {key: "pop_est", fmt: num, scale: "quantile"}],
  [`PIB per capita (${pibAno})`, {key: "pib_pc", fmt: brlCompact, scale: "quantile"}],
  [`Crescimento desde o Censo 2022`, {key: "crescimento", fmt: pct, scale: "diverging"}]
]);
const metricaNome = view(Inputs.radio([...metricas.keys()], {label: "Indicador", value: [...metricas.keys()][0]}));
const ufSel = view(Inputs.select(["Brasil", ...ufs], {label: "Recorte", value: "Brasil"}));
```

```js
const metrica = metricas.get(metricaNome);
const recorte = ufSel === "Brasil" ? featMun : featMun.filter((f) => byCode.get(+f.properties.codarea)?.uf === ufSel);
const valores = new Map(municipios.map((d) => [d.code, d[metrica.key]]));
const colorScale =
  metrica.scale === "diverging"
    ? {type: "diverging", pivot: 0, symmetric: true, interpolate: d3.piecewise(d3.interpolateLab, [pal.diverging.neg, pal.diverging.mid, pal.diverging.pos]), tickFormat: (d) => pct(d)}
    : {type: "quantile", n: 7, range: pal.blues(7), tickFormat: (d) => (metrica.key === "pib_pc" ? brlCompact(d) : numCompact(d))};
```

<div class="card">
  <h2>${metricaNome} — ${ufSel}</h2>
  <h3>${metrica.scale === "quantile" ? "Cores em 7 faixas com o mesmo número de municípios (quantis)" : "Azul: cresceu; vermelho: encolheu em relação ao Censo 2022"}</h3>
  ${resize((width) => choropleth(recorte, valores, {
    width,
    color: colorScale,
    label: metricaNome,
    format: metrica.fmt,
    noData: pal.noData,
    borders: ufSel === "Brasil" ? featUf : null,
    title: (code) => `${byCode.get(code)?.nome} (${byCode.get(code)?.uf})`
  }))}
</div>

```js
const semMalha = qualidade.municipios.fora_da_malha;
```

${semMalha.length ? html`<div class="note">A lista oficial tem ${num(qualidade.municipios.oficiais)} municípios, mas a malha do IBGE ainda traz ${num(qualidade.municipios.na_malha)} polígonos: ${semMalha.map((d) => `${d.nome} (${d.uf}, código ${d.code})`).join(", ")} ainda não aparece no mapa. Municípios criados depois do Censo também não têm população de 2022.</div>` : ""}

## O Censo corrigiu as estimativas

```js
const brasil = d3
  .rollups(popUf, (v) => d3.sum(v, (d) => d.populacao), (d) => d.ano, (d) => d.fonte)
  .flatMap(([ano, fontes]) => fontes.map(([fonte, populacao]) => ({ano, fonte, populacao})))
  .sort((a, b) => a.ano - b.ano);
// Break the line where the series has gaps (no estimates around the census),
// instead of drawing a misleading straight segment across missing years.
const estimativas = brasil
  .filter((d) => d.fonte === "Estimativa")
  .map((d, i, a) => ({...d, trecho: a.slice(0, i + 1).filter((e, j) => j > 0 && e.ano - a[j - 1].ano > 1).length}));
const censo = brasil.filter((d) => d.fonte === "Censo");
const estAntes = d3.greatest(estimativas.filter((d) => d.ano < 2022), (d) => d.ano);
```

<div class="grid grid-cols-2">
  <div class="card">
    <h2>População do Brasil</h2>
    <h3>Estimativas anuais do IBGE (linha) e Censo 2022 (ponto)</h3>
    ${resize((width) => Plot.plot({
      width,
      height: 320,
      marginLeft: 50,
      y: {label: "habitantes (milhões)", grid: true, transform: (d) => d / 1e6, zero: false},
      x: {label: null, tickFormat: "d"},
      marks: [
        Plot.lineY(estimativas, {x: "ano", y: "populacao", z: "trecho", stroke: pal.accent, strokeWidth: 2}),
        Plot.dot(estimativas, {x: "ano", y: "populacao", fill: pal.accent, r: 2.5}),
        Plot.dot(censo, {x: "ano", y: "populacao", r: 6, fill: pal.categorical[1], stroke: "var(--theme-background)", strokeWidth: 2}),
        Plot.text(censo, {x: "ano", y: "populacao", text: (d) => `Censo 2022: ${numCompact(d.populacao)}`, dy: 18, fill: "currentColor"}),
        Plot.tip(estimativas, Plot.pointerX({x: "ano", y: "populacao", title: (d) => `${d.ano}\n${num(d.populacao)} habitantes (estimativa)`}))
      ]
    }))}
    <p class="muted">A última estimativa antes do Censo (${estAntes.ano}) projetava ${numCompact(estAntes.populacao)} habitantes; o Censo contou ${numCompact(censo[0]?.populacao)}. Não há estimativas para os anos em torno do Censo: a série recomeça já ancorada nele.</p>
  </div>
  <div class="card">
    <h2>Crescimento por UF desde o Censo 2022</h2>
    <h3>Variação entre o Censo e a estimativa de ${popAno}</h3>
    ${resize((width) => {
      const cresc = d3.rollups(municipios.filter((d) => d.pop_2022 != null), (v) => d3.sum(v, (d) => d.pop_est) / d3.sum(v, (d) => d.pop_2022) - 1, (d) => d.uf).map(([uf, valor]) => ({uf, valor}));
      return Plot.plot({
        width,
        height: 520,
        marginLeft: 36,
        x: {label: "crescimento", tickFormat: (d) => pct(d), grid: true},
        y: {label: null},
        marks: [
          Plot.barX(cresc, {y: "uf", x: "valor", sort: {y: "-x"}, fill: (d) => (d.valor >= 0 ? pal.diverging.pos : pal.diverging.neg), rx: 3, tip: {format: {x: (d) => pct(d), fill: false}}}),
          Plot.ruleX([0])
        ]
      });
    })}
  </div>
</div>

## Tamanho e riqueza

```js
const destacar = ufSel === "Brasil" ? null : ufSel;
const comDados = municipios.filter((d) => d.pop_est > 0 && d.pib_pc > 0);
```

<div class="card">
  <h2>População × PIB per capita</h2>
  <h3>Cada ponto é um município (escalas logarítmicas)${destacar ? `; em destaque: ${destacar}` : ""}</h3>
  ${resize((width) => Plot.plot({
    width,
    height: 460,
    x: {type: "log", label: `população estimada (${popAno})`, ticks: [1e3, 1e4, 1e5, 1e6, 1e7], tickFormat: (d) => numCompact(d)},
    y: {type: "log", label: `PIB per capita (${pibAno})`, ticks: [5e3, 1e4, 2e4, 5e4, 1e5, 2e5, 5e5], tickFormat: (d) => brlCompact(d), grid: true},
    marks: [
      Plot.dot(comDados, {x: "pop_est", y: "pib_pc", r: 2, fill: destacar ? pal.muted : pal.accent, fillOpacity: destacar ? 0.5 : 0.35}),
      destacar ? Plot.dot(comDados.filter((d) => d.uf === destacar), {x: "pop_est", y: "pib_pc", r: 3.5, fill: pal.accent, stroke: "var(--theme-background)", strokeWidth: 1}) : null,
      Plot.tip(comDados, Plot.pointer({x: "pop_est", y: "pib_pc", title: (d) => `${d.nome} (${d.uf})\n${num(d.pop_est)} habitantes\nPIB per capita: ${brlCompact(d.pib_pc)}`}))
    ]
  }))}
  <p class="muted">PIB per capita de ${pibAno}: o IBGE não publica estimativa de população para 2023, então o denominador é a média entre o Censo 2022 e a estimativa de 2024. Os municípios no topo são, em geral, sedes de refinarias, royalties de petróleo ou grandes indústrias com pouca população.</p>
</div>

## Tabela

```js
const busca = view(Inputs.search(municipios, {placeholder: "Buscar município, UF ou região…", columns: ["nome", "uf", "uf_nome", "regiao"]}));
```

```js
Inputs.table(busca, {
  columns: ["code", "nome", "uf", "regiao", "pop_2022", "pop_est", "crescimento", "pib", "pib_pc"],
  header: {code: "Código IBGE", nome: "Município", uf: "UF", regiao: "Região", pop_2022: "Censo 2022", pop_est: `Estimativa ${popAno}`, crescimento: "Crescimento", pib: `PIB ${pibAno}`, pib_pc: "PIB per capita"},
  format: {code: String, pop_2022: num, pop_est: num, crescimento: pct, pib: brlCompact, pib_pc: brlCompact},
  sort: "pop_est",
  reverse: true,
  rows: 15
})
```
