import * as Plot from "npm:@observablehq/plot";

/**
 * Choropleth of IBGE mesh features (`codarea` property) with Observable Plot.
 *
 * @param features  GeoJSON features to fill (municipalities or UFs)
 * @param value     Map(code -> number)
 * @param options   {color: Plot color scale options, borders: GeoJSON for outlines,
 *                   title: code -> string, format: number -> string, label, width, height}
 */
export function choropleth(features, value, {color, borders, title, format = String, label, width, height, noData = "#ddd"} = {}) {
  const code = (f) => +f.properties.codarea;
  return Plot.plot({
    width,
    height: height ?? Math.min(640, width * 0.95),
    projection: {type: "mercator", domain: {type: "FeatureCollection", features}},
    color: {legend: true, width: Math.min(420, width - 20), label, ...color},
    marks: [
      // Places with no value stay neutral rather than borrowing the lowest color.
      Plot.geo(features, {fill: noData}),
      Plot.geo(
        features.filter((f) => value.get(code(f)) != null),
        Plot.centroid({
          fill: (f) => value.get(code(f)),
          channels: {
            Local: (f) => (title ? title(code(f)) : code(f)),
            [label ?? "Valor"]: (f) => format(value.get(code(f)))
          },
          // The raw fill value is replaced by the formatted channel above.
          tip: {format: {fill: false}}
        })
      ),
      borders ? Plot.geo(borders, {stroke: "var(--theme-background)", strokeWidth: 0.8}) : null
    ]
  });
}
