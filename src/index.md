---
toc: false
---

# Explorador de dados públicos

<p class="lede">IBGE, Câmara dos Deputados e Portal da Transparência — baixados, limpos e cruzados em tempo de build. O site é estático: nenhuma chave de API ou chamada às fontes acontece no seu navegador.</p>

```js
import {brlCompact, num, numCompact, rows} from "./components/format.js";

const municipios = rows(await FileAttachment("data/municipios.parquet").parquet());
const ceap = rows(await FileAttachment("data/ceap.parquet").parquet());
const emendas = rows(await FileAttachment("data/emendas.parquet").parquet());
const deputados = rows(await FileAttachment("data/deputados.parquet").parquet());
const qualidade = FileAttachment("data/qualidade.json").json();
```

```js
const popAno = municipios[0].pop_est_ano;
const ceapAnos = d3.extent(ceap, (d) => d.ano);
const emendasRecentes = emendas.filter((d) => d.ano >= ceapAnos[0]);
```

<div class="grid grid-cols-4">
  <a class="card card-link" href="./municipios">
    <h2>Municípios</h2>
    <span class="big">${num(municipios.length)}</span>
    <p class="muted">${numCompact(d3.sum(municipios, (d) => d.pop_est))} habitantes estimados em ${popAno}</p>
  </a>
  <a class="card card-link" href="./ceap">
    <h2>Cota parlamentar ${ceapAnos.join("–")}</h2>
    <span class="big">${brlCompact(d3.sum(ceap, (d) => d.valor))}</span>
    <p class="muted">reembolsados a ${num(new Set(ceap.map((d) => d.deputado_id).filter((d) => d != null)).size)} deputados</p>
  </a>
  <a class="card card-link" href="./emendas">
    <h2>Emendas pagas ${ceapAnos.join("–")}</h2>
    <span class="big">${brlCompact(d3.sum(emendasRecentes, (d) => d.pago_total))}</span>
    <p class="muted">individuais, de bancada, comissão e relator</p>
  </a>
  <a class="card card-link" href="./perfil">
    <h2>Deputados em exercício</h2>
    <span class="big">${num(deputados.filter((d) => d.em_exercicio).length)}</span>
    <p class="muted">${num(deputados.length)} passaram pela 57ª legislatura</p>
  </a>
</div>

## O que dá para explorar

<div class="grid grid-cols-3">
  <div class="card">
    <h3>Municípios (IBGE)</h3>
    <p>Mapas coropléticos de população, PIB per capita e crescimento desde o Censo 2022, a partir da API SIDRA e da malha territorial do IBGE.</p>
  </div>
  <div class="card">
    <h3>Cota parlamentar e perfis</h3>
    <p>Gastos da CEAP por categoria, partido, UF e fornecedor — e o perfil de cada deputado, juntando gastos, fornecedores e emendas.</p>
  </div>
  <div class="card">
    <h3>Emendas parlamentares</h3>
    <p>Para onde vai o dinheiro das emendas, por município (per capita), função e autor, com autores vinculados aos deputados da Câmara.</p>
  </div>
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
.small { font-size: 0.85rem; }
</style>
