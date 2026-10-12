---
toc: false
---

# Explorador de dados públicos

<p class="lede">IBGE, Câmara dos Deputados e Portal da Transparência — baixados, limpos e cruzados em tempo de build. O site é estático: nenhuma chave de API ou chamada às fontes acontece no seu navegador.</p>

```js
import {brl, brlCompact, MESES, num, numCompact, rows} from "./components/format.js";
import {palette} from "./components/palette.js";
import {choropleth} from "./components/choropleth.js";
import {miniColumns} from "./components/charts.js";
import {grupoPartido, OUTROS, partyColor, PARTIDOS} from "./components/parties.js";

const municipios = rows(await FileAttachment("data/municipios.parquet").parquet());
const popUf = rows(await FileAttachment("data/populacao-uf.parquet").parquet());
const ceap = rows(await FileAttachment("data/ceap.parquet").parquet());
const emendas = rows(await FileAttachment("data/emendas.parquet").parquet());
const emendasMun = rows(await FileAttachment("data/emendas-municipios.parquet").parquet());
const deputados = rows(await FileAttachment("data/deputados.parquet").parquet());
const malhaMun = await FileAttachment("data/malha-municipios.json").json();
const malhaUf = await FileAttachment("data/malha-uf.json").json();
const qualidade = FileAttachment("data/qualidade.json").json();
```

```js
const pal = palette(dark);
const popAno = municipios[0].pop_est_ano;
const ceapAnos = d3.extent(ceap, (d) => d.ano);
const emendasRecentes = emendas.filter((d) => d.ano >= ceapAnos[0]);

// Headline: emendas received per inhabitant since 2019, by municipality and by town size.
const DESDE = 2019;
const munByCode = new Map(municipios.map((d) => [d.code, d]));
const recebido = d3.rollup(emendasMun.filter((d) => d.ano >= DESDE), (v) => d3.sum(v, (d) => d.valor), (d) => d.municipio_code);
const perCapita = new Map([...recebido].filter(([c]) => munByCode.get(c)?.pop_est > 0).map(([c, v]) => [c, v / munByCode.get(c).pop_est]));
const FAIXAS = [
  {nome: "até 20 mil hab.", max: 2e4},
  {nome: "20 a 100 mil", max: 1e5},
  {nome: "100 a 500 mil", max: 5e5},
  {nome: "mais de 500 mil", max: Infinity}
];
const faixaDe = (pop) => FAIXAS.find((f) => pop < f.max).nome;
const porFaixa = FAIXAS.map(({nome}) => {
  const ms = municipios.filter((d) => d.pop_est > 0 && faixaDe(d.pop_est) === nome);
  return {faixa: nome, municipios: ms.length, valor: d3.sum(ms, (d) => recebido.get(d.code) ?? 0) / d3.sum(ms, (d) => d.pop_est)};
});
const pequenas = porFaixa[0];
const medias = porFaixa[2];
```

<div class="card hero">
  <h2 class="hero-title">Cidades com menos de 20 mil habitantes receberam ${brl(pequenas.valor)} por habitante em emendas desde ${DESDE} — ${(pequenas.valor / medias.valor).toLocaleString("pt-BR", {maximumFractionDigits: 1})} vezes o que receberam as de 100 a 500 mil.</h2>
  <div class="hero-grid">
    <div>${resize((width) => choropleth(topojson.feature(malhaMun, malhaMun.objects.BRMU).features, perCapita, {
      width,
      height: Math.min(560, width * 0.95),
      color: {type: "quantile", n: 7, range: pal.blues(7), tickFormat: brl},
      label: `R$ por habitante, ${DESDE}–hoje`,
      format: (v) => `${brl(v)} por habitante`,
      noData: pal.noData,
      borders: topojson.feature(malhaUf, malhaUf.objects.BRUF).features,
      title: (code) => `${munByCode.get(code)?.nome} (${munByCode.get(code)?.uf})`
    }))}</div>
    <div>
      <h3>Por tamanho do município</h3>
      ${resize((width) => Plot.plot({
        width,
        height: 190,
        marginLeft: 104,
        marginRight: 64,
        x: {axis: null},
        y: {label: null, tickSize: 0, domain: FAIXAS.map((f) => f.nome)},
        marks: [
          Plot.barX(porFaixa, {y: "faixa", x: "valor", fill: (d) => (d.faixa === FAIXAS[3].nome ? pal.muted : pal.accent), rx2: 4, insetTop: 6, insetBottom: 6, tip: {format: {x: brl, fill: false}}, channels: {municípios: "municipios"}}),
          Plot.text(porFaixa, {y: "faixa", x: "valor", text: (d) => brl(d.valor), dx: 5, textAnchor: "start", fill: "currentColor", fontSize: 11}),
          Plot.ruleX([0], {strokeOpacity: 0.4})
        ]
      }))}
      <p class="muted small">R$ recebidos por favorecidos sediados em cada município ÷ população. Nas cidades grandes (em cinza) o valor é inflado pelas capitais, onde ficam governos estaduais e órgãos federais que também recebem emendas. <a href="./emendas">Explorar as emendas →</a></p>
    </div>
  </div>
</div>

```js
// Mini-chart data for the cards.
const estimativas = d3
  .rollups(popUf.filter((d) => d.fonte === "Estimativa"), (v) => d3.sum(v, (d) => d.populacao), (d) => d.ano)
  .map(([ano, populacao]) => ({ano, populacao}))
  .sort((a, b) => a.ano - b.ano);
const ceapMensal = d3
  .rollups(ceap.filter((d) => !d.lideranca), (v) => d3.sum(v, (d) => d.valor), (d) => d.ano, (d) => d.mes)
  .flatMap(([ano, ms]) => ms.map(([mes, valor]) => ({data: new Date(Date.UTC(ano, mes - 1, 1)), ano, mes, valor})))
  .sort((a, b) => a.data - b.data);
// The last three months are still receiving receipts; the newest complete one is the highlight.
const ultimoCompleto = d3.utcMonth.offset(d3.max(ceapMensal, (d) => d.data), -3);
const emendasAno = d3.rollups(emendas, (v) => d3.sum(v, (d) => d.pago_total), (d) => d.ano).map(([ano, valor]) => ({ano, valor})).sort((a, b) => a.ano - b.ano);
const bancadas = d3
  .rollups(deputados.filter((d) => d.em_exercicio), (v) => v.length, (d) => grupoPartido(d.partido))
  .map(([partido, n]) => ({partido, n}))
  .sort((a, b) => (a.partido === OUTROS) - (b.partido === OUTROS) || b.n - a.n);
```

<div class="grid grid-cols-4">
  <a class="card card-link" href="./municipios">
    <h2>Municípios</h2>
    <span class="big">${num(municipios.length)}</span>
    <p class="muted">${numCompact(d3.sum(municipios, (d) => d.pop_est))} habitantes estimados em ${popAno}</p>
    ${resize((width) => miniColumns(estimativas, {width, x: "ano", y: "populacao", pal, highlight: (d) => d.ano === popAno, title: (d) => `${d.ano}: ${numCompact(d.populacao)} habitantes`}))}
    <p class="muted small">Estimativas anuais de população do IBGE</p>
  </a>
  <a class="card card-link" href="./ceap">
    <h2>Cota parlamentar ${ceapAnos.join("–")}</h2>
    <span class="big">${brlCompact(d3.sum(ceap, (d) => d.valor))}</span>
    <p class="muted">reembolsados a ${num(new Set(ceap.map((d) => d.deputado_id).filter((d) => d != null)).size)} deputados</p>
    ${resize((width) => miniColumns(ceapMensal, {width, x: "data", y: "valor", interval: "month", pal, highlight: (d) => +d.data === +ultimoCompleto, title: (d) => `${MESES[d.mes - 1]}/${d.ano}: ${brlCompact(d.valor)}`}))}
    <p class="muted small">Gasto por mês; em azul, ${MESES[ultimoCompleto.getUTCMonth()]}/${ultimoCompleto.getUTCFullYear()}, o último mês completo</p>
  </a>
  <a class="card card-link" href="./emendas">
    <h2>Emendas pagas ${ceapAnos.join("–")}</h2>
    <span class="big">${brlCompact(d3.sum(emendasRecentes, (d) => d.pago_total))}</span>
    <p class="muted">individuais, de bancada, comissão e relator</p>
    ${resize((width) => miniColumns(emendasAno, {width, x: "ano", y: "valor", pal, highlight: (d) => d.ano >= ceapAnos[0], title: (d) => `${d.ano}: ${brlCompact(d.valor)}`}))}
    <p class="muted small">Valor pago por ano desde ${emendasAno[0].ano}; em azul, a legislatura atual</p>
  </a>
  <a class="card card-link" href="./perfil">
    <h2>Deputados em exercício</h2>
    <span class="big">${num(deputados.filter((d) => d.em_exercicio).length)}</span>
    <p class="muted">${num(deputados.length)} passaram pela 57ª legislatura</p>
    ${resize((width) => Plot.plot({
      width,
      height: 28,
      margin: 0,
      x: {axis: null},
      y: {axis: null},
      marks: [
        Plot.barX(bancadas, Plot.stackX({x: "n", fill: (d) => partyColor(pal, d.partido), order: null, insetRight: 1, insetLeft: 1, title: (d) => `${d.partido}: ${d.n} deputados`}))
      ]
    }))}
    <div class="legend-row">${bancadas.map((d) => html`<span><i style=${{background: partyColor(pal, d.partido)}}></i>${d.partido} ${d.n}</span>`)}</div>
  </a>
</div>

<div class="grid grid-cols-2">
  <div class="card">
    <h3>Consulta SQL no navegador</h3>
    <p>Os mesmos arquivos Parquet que alimentam os gráficos podem ser consultados com SQL via <a href="./sql">DuckDB-WASM</a>, sem servidor.</p>
  </div>
  <div class="card">
    <h3>Qualidade dos dados</h3>
    <p>${qualidade.favorecidos.correspondencia_municipio.filter((d) => d.match !== "sem correspondência").reduce((s, d) => s + d.parcela, 0).toLocaleString("pt-BR", {style: "percent", maximumFractionDigits: 1})} do valor das emendas por favorecido foi ligado a um código IBGE; ${qualidade.emendas.autores_vinculados_a_deputados} autores de emendas foram ligados a deputados. <a href="./sobre">Veja a metodologia</a>.</p>
  </div>
</div>

<p class="muted small">Dados gerados em ${new Date(qualidade.gerado_em).toLocaleString("pt-BR")}.</p>

<style>
.lede { font-size: 1.15rem; max-width: 52rem; color: var(--theme-foreground-muted); }
.card-link { text-decoration: none; color: inherit; transition: border-color 150ms; }
.card-link:hover { border-color: var(--theme-foreground-focus); }
.card-link svg { display: block; margin-top: 0.75rem; }
.hero { padding: 1.5rem; }
.hero .hero-title { font: 600 clamp(20px, 2.6vw, 28px)/1.25 var(--serif); max-width: 46rem; margin-bottom: 1rem; color: var(--theme-foreground); }
.hero-grid { display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 1fr); gap: 1.5rem; align-items: center; }
.hero-grid h3 { font-weight: 600; color: var(--theme-foreground); }
@media (max-width: 800px) { .hero-grid { grid-template-columns: minmax(0, 1fr); } }
</style>
