# Explorador de dados públicos

A static data site about Brazilian public data — **IBGE**, **Câmara dos Deputados** and **Portal da Transparência** — built with a Python pipeline (**Polars + DuckDB**) and **Observable Framework** (Observable Plot for charts, raw D3 only for the treemap, DuckDB-WASM for in-browser SQL).

Every API call happens **at build time** in Framework data loaders. The browser only downloads pre-cleaned Parquet/JSON files, so no API key, rate limit or pagination ever reaches visitors.

| Page | What it shows | Sources |
|---|---|---|
| Municípios | Choropleths of population, GDP per capita and growth since Censo 2022; census vs. estimates | SIDRA 4709 / 6579 / 5938, malhas v3 |
| Cota parlamentar | CEAP spending by month, category, deputy, party; suppliers; suppliers with active CEIS sanctions | Câmara bulk CSVs, CEIS bulk |
| Perfil do deputado | One deputy: spending, suppliers, CEIS flags, emendas, map of where their emendas landed | All of the above |
| Emendas | Paid emendas by year/type, per-capita map, D3 treemap party → deputy | Portal bulk download |
| Bolsa Família | Families per inhabitant by municipality (**needs API key**) | Portal REST API |
| Consulta SQL | Free-form SQL over all Parquet files with DuckDB-WASM | — |
| Sobre os dados | Methodology and data-quality report (match rates, renamed municipalities…) | — |

## Quick start

Requirements: [uv](https://docs.astral.sh/uv/) and Node.js ≥ 18.

```bash
uv sync          # Python env (polars, duckdb, httpx, pyarrow, pytest)
npm install      # Observable Framework
npm run dev      # http://127.0.0.1:3000 — loaders run on first visit to each page
npm run build    # static site in dist/
```

The first build downloads ≈ 400 MB of zipped CSVs (cached in `data_cache/`, git-ignored) and takes a few minutes; later builds reuse the cache.

## The Portal da Transparência API key (optional)

Everything except the *Bolsa Família* page works **without a key**: emendas and CEIS come from the Portal's keyless bulk downloads.

To enable Bolsa Família:

1. Register at <https://portaldatransparencia.gov.br/api-de-dados/cadastrar-email> — the key arrives by e-mail.
2. `cp .env.example .env` and fill in `PORTAL_TRANSPARENCIA_API_KEY`.
3. Force that loader to rerun: delete `src/.observablehq/cache/data/bolsa-familia.parquet` (or `npm run clean`), then `npm run build`.

The first run makes one request per municipality (~5,600; ≈ 70 min at the default 80 req/min — set `PORTAL_API_RPM` to change). Responses are cached per request, so an interrupted run resumes. The key is sent only as a request header from Python; it never appears in cache file names or outputs. `.env` is git-ignored.

## How it's organised

```
pipeline/            Python package: one module per concern
  http.py            cached downloads (one shared connection), retries, rate limiting, gzip quirks
  schema.py          fails fast with a clear message when a source renames/drops a column
  clean.py           accents, Brazilian numbers, IBGE code normalisation
  ibge.py            SIDRA reshaping, municipalities, meshes
  camara.py          deputies (API) + CEAP (bulk CSVs)
  portal.py          emendas + CEIS (bulk), REST client (key)
  matching.py        record linkage (DuckDB): names -> IBGE codes, authors -> deputies
  frames.py          cleaned frames memoised as Parquet, shared across loaders
  io.py              stdout writers; casts int64 -> int32 so JS doesn't get BigInt
  manifest.py        data manifest (sources, row counts, totals) and build-to-build comparison
src/data/*.py        Framework data loaders (thin; run via `uv run`, see observablehq.config.js)
src/components/      formatting (pt-BR), palette, choropleth (Plot), treemap (D3)
src/*.md             pages
tests/               offline tests for cleaning, SIDRA reshape and matching
```

## Messy-data problems handled

- **Encodings**: CGU files are Latin-1; Câmara files are UTF-8 with BOM.
- **Numbers**: `1.300.000,00` (Portal) vs `1467.50` (Câmara) — one parser, unit-tested.
- **SIDRA**: nested JSON flattened to tidy rows; special symbols (`-` = 0, `X`/`...` = null); the API rejects mixing explicit periods with `-1`.
- **IBGE codes**: UF as `33` or `3300000`, `-1` = national; 6-digit municipality codes mapped to 7 digits.
- **Codes that change over time**: Boa Esperança do Norte‑MT (created 2025) is in the official list (5,571) but not yet in the mesh (5,570) and has no census population.
- **Names without codes**: the emendas-by-beneficiary file has only municipality name + UF. Exact match on a normalised key → rename table (Embu → Embu das Artes, Açu → Assú, Presidente Juscelino → Serra Caiada…) → fuzzy match within the UF. 99.4 % of value matches exactly; ≈ 0.3 % more via aliases/fuzzy.
- **Joining deputies to emendas**: emendas carry an uppercase parliamentary name, not a Câmara id. Names are matched ignoring accents and particles, stripping "(EX-PARLAMENTAR …)" suffixes, and name collisions are broken by legislature and UF. Unmatched individual authors are senators.
- **CEAP sign quirks**: refunds are separate rows; the housing-allowance complement is booked as a negative liquid value.

## Refreshing data

Framework caches each loader's output in `src/.observablehq/cache` and only reruns a loader when its own file changes. The memoised cleaned frames in `data_cache/frames` are keyed by a hash of the `pipeline/` source, so they rebuild automatically after any code change (also in CI, where `data_cache/` is restored from the previous run). Framework's own loader cache doesn't see `pipeline/` changes, though: locally, run `npm run clean` to force the loaders to rerun (it keeps raw downloads). Raw downloads in `data_cache/` expire on their own (3–90 days depending on the source); delete the folder to start fresh.

## Data manifest

Each build writes `manifest.json`: the pipeline code version, the commit, when each raw source was downloaded, and row counts / totals (overall and per year) of every cleaned table. `npm run build` copies it to a stable path, `dist/manifest.json`, so it is served at `<site>/manifest.json`.

In CI, before deploying, the workflow downloads the live manifest and runs

```bash
uv run python -m pipeline.manifest compare previous-manifest.json dist/manifest.json
```

The changed metrics go to the job summary. Drops above 10 %, metrics that disappear (e.g. a whole CEAP year) and removed output columns become warnings. Add `--strict` in the workflow to block the deploy on warnings.

## Tests

```bash
uv run pytest
```

## About Observable Framework

Framework is open source and still released (1.13.x, 2026) but sees low activity. For a build-time static site this is a modest risk: the pipeline is plain Python writing Parquet, so moving to another static generator (or SvelteKit + Plot) would only mean rewriting the pages.
