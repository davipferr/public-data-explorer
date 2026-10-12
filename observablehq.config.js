// See https://observablehq.com/framework/config for documentation.
export default {
  title: "Explorador de dados públicos",
  root: "src",
  lang: "pt-BR",
  pages: [
    {name: "Municípios (IBGE)", path: "/municipios"},
    {name: "Cota parlamentar (Câmara)", path: "/ceap"},
    {name: "Perfil do deputado", path: "/perfil"},
    {name: "Emendas parlamentares", path: "/emendas"},
    {name: "Bolsa Família (API)", path: "/bolsa-familia"},
    {name: "Consulta SQL", path: "/sql"},
    {name: "Sobre os dados", path: "/sobre"}
  ],
  head: [
    '<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>📊</text></svg>">',
    '<link rel="preconnect" href="https://fonts.googleapis.com">',
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&family=Source+Serif+4:opsz,wght@8..60,600;8..60,700&display=swap">'
  ].join("\n"),
  // Theme imports + typography live in src/style.css.
  style: "style.css",
  footer: "Dados: IBGE, Câmara dos Deputados, Portal da Transparência (CGU). Processados em tempo de build com Polars + DuckDB.",
  toc: true,
  search: true,
  // Python loaders run inside the uv-managed environment, so `import pipeline`
  // works and nobody needs a global Python setup. `-X utf8` keeps stderr logs
  // with accents from crashing on Windows consoles.
  interpreters: {
    ".py": ["uv", "run", "--quiet", "python", "-X", "utf8"]
  }
};
