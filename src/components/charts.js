import * as Plot from "npm:@observablehq/plot";
import * as d3 from "npm:d3";
import {brl, brlCompact} from "./format.js";

/** Cut a label to `n` characters with an ellipsis (the tooltip keeps the full text). */
export function truncate(text, n) {
  const s = String(text ?? "");
  return s.length > n ? `${s.slice(0, Math.max(1, n - 1)).trimEnd()}…` : s;
}

/** Left margin for bar labels: up to `max`, and at most ~45 % of a narrow chart. */
export function labelMargin(width, max = 200) {
  return Math.round(Math.max(72, Math.min(max, width * 0.45)));
}

/**
 * Horizontal bars, sorted, with the value printed at the end of each bar instead
 * of an x axis. Labels on the left are truncated to fit the (responsive) margin.
 *
 * @param data  array of objects
 * @param opts  {width, y: field or accessor, x: field, fill: colour or channel,
 *               color: Plot colour scale, format: value -> label text,
 *               limit: keep the top N, href, maxMargin, channels}
 */
export function hbars(data, {width, y, x = "valor", fill, color, format = brlCompact, limit, href, maxMargin = 200, channels} = {}) {
  const yOf = typeof y === "function" ? y : (d) => d[y];
  const rows = [...data].filter((d) => d[x] != null).sort((a, b) => b[x] - a[x]).slice(0, limit ?? Infinity);
  const marginLeft = labelMargin(width, maxMargin);
  const chars = Math.floor((marginLeft - 8) / 5.6); // ~5.6 px per character at Plot's 10px
  return Plot.plot({
    width,
    height: rows.length * 26 + 12,
    marginLeft,
    marginRight: 70,
    marginTop: 4,
    marginBottom: 4,
    x: {axis: null},
    y: {label: null, tickSize: 0, tickFormat: (d) => truncate(d, chars), domain: rows.map(yOf)},
    color,
    marks: [
      Plot.barX(rows, {y: yOf, x, fill, href, channels, rx2: 4, insetTop: 2, insetBottom: 2, tip: {format: {x: brl, fill: !!color}}}),
      Plot.text(rows, {y: yOf, x, text: (d) => format(d[x]), dx: 5, textAnchor: "start", fill: "currentColor", fontSize: 11}),
      Plot.ruleX([0], {strokeOpacity: 0.4})
    ]
  });
}

// First rounds of the elections inside (or near) the data's period.
export const ELEICOES = [
  {data: new Date(Date.UTC(2022, 9, 2)), nome: "Eleições gerais"},
  {data: new Date(Date.UTC(2024, 9, 6)), nome: "Eleições municipais"},
  {data: new Date(Date.UTC(2026, 9, 4)), nome: "Eleições gerais"}
];

/**
 * Hairline + label for each election inside the months [start, end]. Pair with
 * `y: {insetTop: 22}`. Charts narrower than 640 px label just the year, so
 * neighbouring elections don't collide (say what the lines are in the caption).
 */
export function eleicoesMarks([start, end], {width = Infinity} = {}) {
  const ev = ELEICOES.filter((e) => e.data >= start && e.data < d3.utcMonth.offset(end, 1));
  // Labels near the right edge go on the left of their line so they aren't cut off.
  const late = (e) => e.data > +start + 0.8 * (end - start);
  const text = width < 640 ? (d) => String(d.data.getUTCFullYear()) : (d) => `${d.nome} ${d.data.getUTCFullYear()}`;
  const label = (data, textAnchor, dx) => Plot.text(data, {x: "data", text, frameAnchor: "top", textAnchor, dx, fill: "currentColor", fontSize: 11});
  return [
    Plot.ruleX(ev, {x: "data", stroke: "currentColor", strokeOpacity: 0.45}),
    label(ev.filter((e) => !late(e)), "start", 4),
    label(ev.filter(late), "end", -4)
  ];
}

/** Label the tallest month of a monthly series ({data, valor}). */
export function picoMark(mensal, format) {
  const pico = d3.greatest(mensal, (d) => d.valor);
  if (!pico) return null;
  return Plot.text([pico], {
    x: (d) => d3.utcDay.offset(d.data, 15),
    y: "valor",
    text: format,
    dy: -6,
    lineAnchor: "bottom",
    fill: "currentColor",
    fontSize: 11,
    stroke: "var(--theme-background-alt)",
    strokeWidth: 3,
    paintOrder: "stroke"
  });
}

/**
 * Compact chart for a stat tile: no axes, a hover tooltip, the de-emphasis hue
 * with the `highlight(d)` items in the accent.
 */
export function miniColumns(data, {width, x, y, highlight = () => false, pal, title, height = 64, interval}) {
  return Plot.plot({
    width,
    height,
    margin: 0,
    marginTop: 4,
    x: {axis: null, ...(interval ? {} : {type: "band", padding: 0.2})},
    y: {axis: null},
    marks: [
      (interval ? Plot.rectY : Plot.barY)(data, {
        x,
        y,
        ...(interval ? {interval, inset: 0.75} : {}),
        fill: (d) => (highlight(d) ? pal.accent : pal.muted),
        ry2: 2,
        tip: false
      }),
      Plot.tip(data, Plot.pointerX({x: interval ? (d) => d[x] : x, y, title}))
    ]
  });
}
