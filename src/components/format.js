import * as d3 from "npm:d3";

// Brazilian number conventions: "." for thousands, "," for decimals, "R$ " prefix.
export const locale = d3.formatLocale({
  decimal: ",",
  thousands: ".",
  grouping: [3],
  currency: ["R$ ", ""]
});

const int = locale.format(",.0f");
const dec1 = locale.format(",.1~f"); // "1,5" but "20", not "20,0"
const pct1 = locale.format(".1%");

export const num = (x) => (x == null || Number.isNaN(x) ? "–" : int(x));
export const pct = (x) => (x == null || Number.isNaN(x) ? "–" : pct1(x));
export const brl = (x) => (x == null || Number.isNaN(x) ? "–" : `R$ ${int(x)}`);

/** Compact BRL: R$ 1,2 mi · R$ 3,4 bi · R$ 950 mil */
export function brlCompact(x) {
  if (x == null || Number.isNaN(x)) return "–";
  const a = Math.abs(x);
  if (a >= 1e9) return `R$ ${dec1(x / 1e9)} bi`;
  if (a >= 1e6) return `R$ ${dec1(x / 1e6)} mi`;
  if (a >= 1e3) return `R$ ${int(x / 1e3)} mil`;
  return `R$ ${int(x)}`;
}

/** Compact count: 1,2 mi · 35 mil */
export function numCompact(x) {
  if (x == null || Number.isNaN(x)) return "–";
  const a = Math.abs(x);
  if (a >= 1e6) return `${dec1(x / 1e6)} mi`;
  if (a >= 1e4) return `${int(x / 1e3)} mil`;
  return int(x);
}

export const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

/** Arrow table -> array of plain objects (Plot/D3 want plain objects). */
export function rows(table) {
  return Array.from(table, (r) => r.toJSON());
}

/** Result count for Inputs.search (its default label is English). */
export const resultados = (n) => (n === 0 ? "nenhum resultado" : `${int(n)} resultado${n === 1 ? "" : "s"}`);
