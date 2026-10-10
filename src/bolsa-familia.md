---
title: Bolsa Família (API)
---

# Bolsa Família por município

Esta página usa a **API REST do Portal da Transparência**, que exige uma chave pessoal (gratuita, cadastrada por e-mail) e tem limite de requisições por minuto. Por isso a consulta acontece só no build: a chave fica no seu computador ou no segredo do CI e nunca chega ao navegador.

```js
import {brl, brlCompact, num, numCompact, rows} from "./components/format.js";
import {palette} from "./components/palette.js";
import {choropleth} from "./components/choropleth.js";

const bf = rows(await FileAttachment("data/bolsa-familia.parquet").parquet());
const municipios = rows(await FileAttachment("data/municipios.parquet").parquet());
const pal = palette(dark);
```

```js
const disponivel = bf.length > 0;
```

```js
if (!disponivel) display(html`<div class="tip">
  <p><strong>Dados ainda não carregados: falta a chave da API.</strong></p>
  <ol>
    <li>Cadastre-se em <a href="https://portaldatransparencia.gov.br/api-de-dados/cadastrar-email" target="_blank" rel="noopener">portaldatransparencia.gov.br/api-de-dados</a> — a chave chega por e-mail.</li>
    <li>Copie <code>.env.example</code> para <code>.env</code> e preencha <code>PORTAL_TRANSPARENCIA_API_KEY</code>.</li>
    <li>Rode <code>npm run clean</code> e <code>npm run build</code>. A primeira execução faz ~5,6 mil chamadas (≈70 min a 80 req/min); as respostas ficam em cache e as execuções seguintes são instantâneas.</li>
  </ol>
</div>`);
```

```js
const malhaMun = disponivel ? await FileAttachment("data/malha-municipios.json").json() : null;
const malhaUf = disponivel ? await FileAttachment("data/malha-uf.json").json() : null;
```

```js
const mes = disponivel ? bf[0].mes_ano : null;
const pop = new Map(municipios.map((d) => [d.code, d.pop_est]));
const munByCode = new Map(municipios.map((d) => [d.code, d]));
const porMun = d3.rollup(bf, (v) => ({valor: d3.sum(v, (d) => d.valor), beneficiarios: d3.sum(v, (d) => d.beneficiarios)}), (d) => d.municipio_code);
const cobertura = new Map([...porMun].filter(([c]) => pop.get(c) > 0).map(([c, d]) => [c, d.beneficiarios / pop.get(c)]));
```

```js
if (disponivel) {
  display(html`<div class="grid grid-cols-3">
    <div class="card"><h2>Pago em ${mes.slice(4)}/${mes.slice(0, 4)}</h2><span class="big">${brlCompact(d3.sum(bf, (d) => d.valor))}</span></div>
    <div class="card"><h2>Famílias beneficiárias</h2><span class="big">${numCompact(d3.sum(bf, (d) => d.beneficiarios))}</span></div>
    <div class="card"><h2>Benefício médio</h2><span class="big">${brl(d3.sum(bf, (d) => d.valor) / d3.sum(bf, (d) => d.beneficiarios))}</span></div>
  </div>`);
  display(html`<div class="card">
    <h2>Famílias beneficiárias por habitante</h2>
    ${resize((width) => choropleth(topojson.feature(malhaMun, malhaMun.objects.BRMU).features, cobertura, {
      width,
      color: {type: "quantile", n: 7, range: pal.blues(7), tickFormat: (d) => d.toLocaleString("pt-BR", {style: "percent", maximumFractionDigits: 0})},
      label: "Famílias / habitantes",
      format: (v) => v.toLocaleString("pt-BR", {style: "percent", maximumFractionDigits: 1}),
      noData: pal.noData,
      borders: topojson.feature(malhaUf, malhaUf.objects.BRUF).features,
      title: (code) => `${munByCode.get(code)?.nome} (${munByCode.get(code)?.uf})`
    }))}
  </div>`);
}
```

## Como a chave é protegida

- O loader `src/data/bolsa-familia.parquet.py` lê a chave de `PORTAL_TRANSPARENCIA_API_KEY` (variável de ambiente ou `.env`, que está no `.gitignore`).
- A chave vai só no cabeçalho `chave-api-dados` das requisições feitas pelo Python; ela não entra no nome dos arquivos de cache nem em nenhuma saída.
- O site publicado contém apenas o Parquet resultante. Os outros dados do Portal (emendas, CEIS) vêm do download em massa, que não exige chave.
