// Party colours. The seven largest benches of the 57th legislature get the
// first seven categorical slots, in this fixed order; every other party is
// "Outros" in neutral grey. The list is fixed (not ranked per chart), so a party
// keeps its colour on every page and under every filter.
export const PARTIDOS = ["PL", "PT", "UNIÃO", "PSD", "PP", "REPUBLICANOS", "MDB"];
export const OUTROS = "Outros";

export const grupoPartido = (partido) => (PARTIDOS.includes(partido) ? partido : OUTROS);

/** Plot color scale options: `fill: (d) => grupoPartido(d.partido)` + `color: partyScale(pal)`. */
export function partyScale(pal, options = {}) {
  return {domain: [...PARTIDOS, OUTROS], range: [...pal.categorical.slice(0, PARTIDOS.length), pal.muted], ...options};
}

/** Colour of one party (for HTML: header strips, swatches). */
export function partyColor(pal, partido) {
  const i = PARTIDOS.indexOf(partido);
  return i >= 0 ? pal.categorical[i] : pal.muted;
}
