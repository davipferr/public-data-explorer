---
title: Sobre os dados
---

# Sobre os dados

```js
import {brlCompact, num, pct} from "./components/format.js";
const q = await FileAttachment("data/qualidade.json").json();
```

Este é um site estático. Os dados são baixados e limpos **em tempo de build** por *data loaders* em Python (Polars + DuckDB) do Observable Framework; o navegador recebe apenas arquivos Parquet/JSON prontos. Última geração: **${new Date(q.gerado_em).toLocaleString("pt-BR")}**.

## Fontes

| Fonte | Acesso | O que usamos |
|---|---|---|
| IBGE — SIDRA (`servicodados.ibge.gov.br/api/v3/agregados`) | API pública | População (Censo 2022, tabela 4709; estimativas, 6579) e PIB municipal (5938) |
| IBGE — Localidades e Malhas (`/api/v1/localidades`, `/api/v3/malhas`) | API pública | Lista oficial de municípios e TopoJSON de UFs e municípios |
| Câmara — dados abertos | Arquivos em massa + API (só a lista de deputados) | CEAP de ${q.ceap.anos.join(", ")}; cadastro de deputados |
| Portal da Transparência — downloads | Arquivos em massa, sem chave | Emendas parlamentares (${q.emendas.anos[0]}–${q.emendas.anos.at(-1)}) e CEIS (snapshot de ${new Date(q.ceis.snapshot + "T12:00").toLocaleDateString("pt-BR")}) |
| Portal da Transparência — API | Chave pessoal, só no build | Bolsa Família por município — <strong>${q.portal_api.chave_configurada ? "chave configurada" : "chave não configurada"}</strong> |

## Limpeza

- **Codificação.** Os arquivos da CGU vêm em Latin-1 (Windows-1252) e são convertidos para UTF-8 antes da leitura; os da Câmara já são UTF-8 com BOM.
- **Números.** O Portal usa formato brasileiro (`1.300.000,00`); a Câmara usa ponto decimal (`1467.50`). Um único parser trata os dois casos (vírgula presente → pontos são milhar; senão, ponto com exatamente 3 dígitos depois → milhar; senão, decimal).
- **Sinais do SIDRA.** `-` é zero absoluto; `..`, `...` e `X` (sigilo) viram nulo.
- **Códigos IBGE.** UF aparece como `33` ou `3300000`; `-1` significa “nacional”. Municípios com 6 dígitos (sem o dígito verificador) são mapeados pelos 6 primeiros dígitos da lista oficial.
- **Sinais da CEAP.** Reembolsos posteriores (`vlrRestituicao`) são descontados; o complemento de auxílio-moradia vem com valor líquido negativo e é tratado como despesa; créditos de passagens aéreas canceladas permanecem negativos.
- **Nomes.** Comparações usam uma chave sem acentos, em maiúsculas e sem pontuação (`Alta Floresta D'Oeste` → `ALTA FLORESTA D OESTE`).

## Cruzamentos e sua qualidade

### Municípios que mudam com o tempo

A lista oficial tem **${num(q.municipios.oficiais)}** municípios; a malha territorial, **${num(q.municipios.na_malha)}** polígonos.

```js
q.municipios.fora_da_malha.length
  ? html`<p>Fora da malha: ${q.municipios.fora_da_malha.map((d) => `${d.nome} (${d.uf}, ${d.code})`).join(", ")}. Municípios criados depois de 2022 também não têm população do Censo nem PIB.</p>`
  : html`<p>Todos os municípios oficiais estão na malha.</p>`
```

### Município do favorecido → código IBGE

O arquivo de emendas por favorecido traz o município só como nome + UF. A ligação é feita em três passos: nome normalizado exato, tabela de renomeações (Embu → Embu das Artes, Açu → Assú, Presidente Juscelino → Serra Caiada…) e, por fim, o nome mais parecido dentro da mesma UF (similaridade ≥ 0,85).

```js
Inputs.table(q.favorecidos.correspondencia_municipio, {
  columns: ["match", "linhas", "valor", "parcela"],
  header: {match: "Método", linhas: "Linhas", valor: "Valor", parcela: "Parcela do valor"},
  format: {linhas: num, valor: brlCompact, parcela: pct},
  layout: "auto"
})
```

<details>
<summary>Nomes corrigidos por renomeação ou aproximação (${q.favorecidos.nomes_corrigidos.length})</summary>

```js
Inputs.table(q.favorecidos.nomes_corrigidos, {
  columns: ["uf", "municipio_nome", "nome_ibge", "match"],
  header: {uf: "UF", municipio_nome: "Nome no Portal", nome_ibge: "Nome no IBGE", match: "Método"},
  layout: "auto",
  rows: 30
})
```

</details>

### Autor da emenda → deputado

Emendas trazem o nome parlamentar em maiúsculas, sem identificador da Câmara. A chave de comparação remove acentos, partículas (*da, de, do…*) e o sufixo “(EX-PARLAMENTAR …)” usado quando a emenda passa a um sucessor. Quando dois deputados têm o mesmo nome parlamentar, vale o da legislatura em que a emenda foi apresentada (ano anterior ao orçamento) e da mesma UF.

Resultado: **${num(q.emendas.autores_vinculados_a_deputados)}** de **${num(q.emendas.autores_individuais)}** autores de emendas individuais foram ligados a deputados das legislaturas 55–57. Os demais são, em sua grande maioria, senadores.

### Escopo das emendas

Nem toda emenda tem município de destino — boa parte é destinada a “múltiplos” municípios ou a um estado. Por isso o mapa de emendas usa o arquivo por favorecido.

```js
Inputs.table(q.emendas.por_escopo, {
  columns: ["escopo", "linhas", "valor", "parcela"],
  header: {escopo: "Localidade de aplicação", linhas: "Linhas", valor: "Valor pago", parcela: "Parcela"},
  format: {linhas: num, valor: brlCompact, parcela: pct},
  layout: "auto"
})
```

### CEAP × CEIS

Despesas são ligadas a sanções pelo CNPJ/CPF do fornecedor, apenas quando a data de emissão da nota cai dentro do período da sanção. O CEIS é um snapshot atual: sanções já excluídas do cadastro não aparecem.

## Limitações

- A CEAP é agregada por deputado, mês e categoria (o detalhe de cada nota não é publicado no site, para manter os arquivos leves). Partido e UF são os registrados em cada despesa.
- Os meses mais recentes da CEAP estão incompletos: deputados têm até 90 dias para apresentar notas.
- O PIB per capita de 2023 usa como denominador a média entre o Censo 2022 e a estimativa de 2024, porque o IBGE não publicou estimativa para 2023.
- Valores são nominais (sem correção pela inflação).
