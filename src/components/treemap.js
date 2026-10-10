import * as d3 from "npm:d3";

/**
 * Two-level treemap (group -> item), drawn with raw D3 because Observable Plot
 * has no hierarchical layout.
 *
 * Groups get categorical hues in fixed order (folded to `maxGroups`, the rest
 * as "Outros"); items are the cells. Hover shows a tooltip; cells too small
 * for a label stay unlabeled.
 *
 * @param data   [{group, item, value}]
 * @param opts   {width, height, colors: string[], format: number -> string}
 */
export function treemap(data, {width, height = 480, colors, format = String, maxGroups = 6} = {}) {
  // Fold small groups into "Outros" so we never generate a 9th hue.
  const totals = d3.rollups(data, (v) => d3.sum(v, (d) => d.value), (d) => d.group).sort((a, b) => b[1] - a[1]);
  const keep = new Set(totals.slice(0, maxGroups).map(([g]) => g));
  const folded = data.map((d) => (keep.has(d.group) ? d : {...d, group: "Outros"}));
  const groups = [...keep, ...(folded.some((d) => d.group === "Outros") ? ["Outros"] : [])];
  const color = d3.scaleOrdinal(groups, [...colors.slice(0, maxGroups), "var(--theme-foreground-faint)"]);

  const tree = {
    name: "root",
    children: d3.rollups(
      folded.filter((d) => d.value > 0),
      (v) => d3.rollups(v, (w) => d3.sum(w, (d) => d.value), (d) => d.item).map(([name, value]) => ({name, value})),
      (d) => d.group
    ).map(([name, children]) => ({name, children}))
  };
  const root = d3.hierarchy(tree).sum((d) => d.value ?? 0).sort((a, b) => b.value - a.value);

  d3.treemap().size([width, height]).paddingInner(2).paddingTop(18).round(true)(root);
  const total = root.value;

  const svg = d3
    .create("svg")
    .attr("viewBox", [0, 0, width, height])
    .attr("width", width)
    .attr("height", height)
    .attr("style", "max-width: 100%; height: auto; font: 11px var(--sans-serif); overflow: visible;");

  // Group headers.
  const groupNodes = root.children ?? [];
  svg
    .append("g")
    .selectAll("text")
    .data(groupNodes.filter((g) => g.x1 - g.x0 > 60))
    .join("text")
    .attr("x", (g) => g.x0 + 2)
    .attr("y", (g) => g.y0 + 13)
    .attr("fill", "currentColor")
    .attr("font-weight", 600)
    .text((g) => `${g.data.name} · ${format(g.value)}`)
    .each(function (g) {
      clip(this, g.x1 - g.x0 - 4);
    });

  const leaf = svg
    .append("g")
    .selectAll("g")
    .data(root.leaves())
    .join("g")
    .attr("transform", (d) => `translate(${d.x0},${d.y0})`);

  leaf
    .append("rect")
    .attr("width", (d) => Math.max(0, d.x1 - d.x0))
    .attr("height", (d) => Math.max(0, d.y1 - d.y0))
    .attr("rx", 3)
    .style("fill", (d) => color(d.parent.data.name))
    .attr("fill-opacity", 0.85);

  leaf
    .append("title")
    .text((d) => `${d.parent.data.name}\n${d.data.name}\n${format(d.value)} (${((d.value / total) * 100).toFixed(1).replace(".", ",")}%)`);

  leaf
    .filter((d) => d.x1 - d.x0 > 70 && d.y1 - d.y0 > 30)
    .append("text")
    .attr("x", 4)
    .attr("y", 14)
    .attr("fill", "white")
    .call((t) => t.append("tspan").attr("font-weight", 600).text((d) => d.data.name))
    .call((t) => t.append("tspan").attr("x", 4).attr("dy", 13).attr("fill-opacity", 0.85).text((d) => format(d.value)))
    .each(function (d) {
      for (const span of this.querySelectorAll("tspan")) clip(span, d.x1 - d.x0 - 8);
    });

  return svg.node();
}

// Truncate an SVG text node with an ellipsis so it fits in `maxWidth` pixels.
function clip(node, maxWidth) {
  let text = node.textContent;
  if (!node.getComputedTextLength) return;
  // getComputedTextLength needs the node in the DOM; when detached it returns 0
  // and we fall back to a character estimate (~6.2 px per char at 11px).
  const measure = () => node.getComputedTextLength() || text.length * 6.2;
  while (text.length > 1 && measure() > maxWidth) {
    text = text.slice(0, -2);
    node.textContent = text + "…";
  }
}
