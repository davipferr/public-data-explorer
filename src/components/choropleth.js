import * as Plot from "npm:@observablehq/plot";
import * as d3 from "npm:d3";
import {html} from "npm:htl";

/**
 * Choropleth of IBGE mesh features (`codarea` property) with Observable Plot,
 * an inset legend and hover / click interaction.
 *
 * Quantile colour scales are turned into explicit thresholds so the legend can
 * label each class with its range ("R$ 120 – R$ 340"); places without a value
 * get the `noData` grey, with its own legend swatch.
 *
 * @param features  GeoJSON features to fill (municipalities or UFs)
 * @param value     Map(code -> number)
 * @param options   {color: Plot colour scale options (type "quantile" with n + range,
 *                   or any continuous type), borders: GeoJSON features drawn as
 *                   outlines on top, title: code -> string, format: number -> string,
 *                   label, width, height, noData, onSelect: code -> void (click)}
 */
export function choropleth(features, value, {color = {}, borders, title, format = String, label = "Valor", width, height, noData = "#ddd", onSelect} = {}) {
  const code = (f) => +f.properties.codarea;
  const valueOf = (f) => value.get(code(f));
  const withValue = features.filter((f) => valueOf(f) != null);
  const tickFormat = color.tickFormat ?? format;

  // Quantile -> threshold: same classes Plot would compute, but we know the breaks.
  let scale = color;
  let classes = null;
  if (color.type === "quantile") {
    const breaks = [...new Set(d3.scaleQuantile(withValue.map(valueOf), color.range).quantiles())];
    const range = pick(color.range, breaks.length + 1);
    scale = {type: "threshold", domain: breaks, range};
    classes = range.map((fill, i) => ({
      fill,
      text: i === 0 ? `até ${tickFormat(breaks[0])}` : i === breaks.length ? `acima de ${tickFormat(breaks[i - 1])}` : `${tickFormat(breaks[i - 1])} – ${tickFormat(breaks[i])}`
    }));
  }

  const tipText = (f) => {
    const v = valueOf(f);
    return `${title ? title(code(f)) : code(f)}\n${label}: ${v == null ? "sem dados" : format(v)}${onSelect ? "\nclique para ampliar" : ""}`;
  };

  const plot = Plot.plot({
    width,
    height: height ?? Math.min(640, width * 0.95),
    projection: {type: "mercator", domain: {type: "FeatureCollection", features}},
    color: {...scale, legend: false, tickFormat: undefined},
    marks: [
      // Places with no value stay neutral rather than borrowing the lowest colour.
      Plot.geo(features, {fill: noData}),
      Plot.geo(withValue, {fill: valueOf}),
      borders ? Plot.geo(borders, {stroke: "currentColor", strokeOpacity: 0.5, strokeWidth: 0.6}) : null,
      // Hover: outline the municipality under the pointer, and a tooltip.
      Plot.geo(features, Plot.pointer(Plot.centroid({stroke: "currentColor", strokeWidth: 1.5}))),
      Plot.tip(features, Plot.pointer(Plot.centroid({title: tipText})))
    ]
  });

  if (onSelect) {
    plot.style.cursor = "pointer";
    plot.addEventListener("click", () => plot.value && onSelect(code(plot.value)));
  }

  const missing = withValue.length < features.length;
  const swatch = (fill, text) => html`<div class="item"><span class="swatch" style=${{background: fill}}></span>${text}</div>`;
  const legend = html`<div class="choropleth-legend">
    <div class="title">${label}</div>
    ${classes
      ? classes.map((c) => swatch(c.fill, c.text))
      : plot.legend("color", {width: Math.min(260, width - 20), label: null, tickFormat, marginLeft: 6, marginRight: 12})}
    ${missing ? swatch(noData, "sem dados") : null}
  </div>`;

  return html`<div class="choropleth">${plot}${legend}</div>`;
}

// n evenly spaced items of `range`, keeping both ends.
function pick(range, n) {
  if (n >= range.length) return range.slice(0, n);
  if (n === 1) return [range.at(-1)];
  return Array.from({length: n}, (_, i) => range[Math.round((i * (range.length - 1)) / (n - 1))]);
}
