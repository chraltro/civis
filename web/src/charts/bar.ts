/**
 * Horizontal bar chart for a country ranking. Generic over the value: pass a
 * `valueOf(iso) -> number | null` and an optional ordering. Used for the
 * Overview composite ranking and for per-domain rankings.
 */

import * as d3 from "d3";
import type { CivisData } from "../data";
import { state } from "../state";
import { hideTooltip, showTooltip } from "./tooltip";

const COL = {
  inkFaint: "#6e7869",
  sage: "#94b09e",
  sageSoft: "#6d8a78",
  amber: "#d2965a",
  grid: "#2a3a32",
};

function isMobile(): boolean {
  return window.innerWidth < 600;
}

export interface BarOpts {
  selector: string;
  data: CivisData;
  valueOf: (iso: string) => number | null;
  /** Optional title shown above the chart, in the panel header. */
  formatValue?: (v: number) => string;
}

export function drawBar(opts: BarOpts): void {
  const svg = d3.select<SVGSVGElement, unknown>(opts.selector);
  svg.selectAll("*").remove();

  const mobile = isMobile();
  const W = mobile ? 420 : 720;
  const H = mobile ? 900 : 640;
  const margin = mobile
    ? { top: 6, right: 50, bottom: 32, left: 110 }
    : { top: 6, right: 56, bottom: 32, left: 130 };
  const innerW = W - margin.left - margin.right;
  const innerH = H - margin.top - margin.bottom;
  svg.attr("viewBox", `0 0 ${W} ${H}`);
  const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);

  const fmt = opts.formatValue ?? ((v) => (v >= 0 ? "+" : "") + v.toFixed(2));
  const rows = opts.data.countries
    .map((c) => ({ iso: c.iso, name: c.name, v: opts.valueOf(c.iso) }))
    .filter((r): r is { iso: string; name: string; v: number } => r.v != null)
    .sort((a, b) => b.v - a.v);

  const maxV = d3.max(rows, (d) => Math.abs(d.v)) ?? 1;
  const minV = d3.min(rows, (d) => d.v) ?? 0;
  const lo = Math.min(0, Math.floor(minV * 10) / 10);
  const hi = Math.ceil(maxV * 10) / 10;

  const x = d3.scaleLinear().domain([lo, hi * 1.05]).range([0, innerW]);
  const y = d3
    .scaleBand<string>()
    .domain(rows.map((d) => d.iso))
    .range([0, innerH])
    .padding(0.32);

  const tickVals = d3.range(lo, hi + 0.001, 0.5);
  g.append("g")
    .attr("class", "grid")
    .selectAll("line")
    .data(tickVals)
    .join("line")
    .attr("x1", (d) => x(d))
    .attr("x2", (d) => x(d))
    .attr("y1", 0)
    .attr("y2", innerH);

  g.append("line")
    .attr("class", "baseline")
    .attr("x1", x(0))
    .attr("x2", x(0))
    .attr("y1", 0)
    .attr("y2", innerH);

  const cls = (iso: string) =>
    iso === state.hlA ? "hl-a" : iso === state.hlB ? "hl-b" : "";
  const fill = (iso: string) => {
    if (iso === state.hlB) return COL.amber;
    if (iso === state.hlA) return "#b8c9bd";
    return COL.sageSoft;
  };

  // Wide transparent hover zone per row, behind the visible bar/labels.
  g.selectAll("rect.row-hit")
    .data(rows)
    .join("rect")
    .attr("class", "row-hit")
    .attr("x", -margin.left + 4)
    .attr("y", (d) => y(d.iso)! - y.step() * 0.16)
    .attr("width", innerW + margin.left + margin.right - 8)
    .attr("height", y.step() * 0.96)
    .attr("fill", "transparent")
    .style("cursor", "default")
    .on("mouseenter", (e, d) => {
      const rect = (e.currentTarget as SVGRectElement).getBoundingClientRect();
      showTooltip(
        `<div class="tt-yr">${d.name}</div><div class="tt-v">${fmt(d.v)}</div>`,
        e.clientX,
        rect.top,
      );
    })
    .on("mousemove", (e, d) => {
      const rect = (e.currentTarget as SVGRectElement).getBoundingClientRect();
      showTooltip(
        `<div class="tt-yr">${d.name}</div><div class="tt-v">${fmt(d.v)}</div>`,
        e.clientX,
        rect.top,
      );
    })
    .on("mouseleave", () => hideTooltip());

  g.selectAll("rect.bar")
    .data(rows)
    .join("rect")
    .attr("class", (d) => "bar " + cls(d.iso))
    .attr("x", (d) => x(Math.min(0, d.v)))
    .attr("y", (d) => y(d.iso)!)
    .attr("width", (d) => Math.max(0.5, Math.abs(x(d.v) - x(0))))
    .attr("height", y.bandwidth())
    .attr("fill", (d) => fill(d.iso))
    .attr("opacity", (d) => (d.iso === state.hlA || d.iso === state.hlB ? 1 : 0.78))
    .style("pointer-events", "none");

  g.selectAll("text.cl")
    .data(rows)
    .join("text")
    .attr("class", (d) => "country-label-bar " + cls(d.iso))
    .attr("x", -8)
    .attr("y", (d) => y(d.iso)! + y.bandwidth() / 2 + 0.5)
    .attr("dy", "0.35em")
    .attr("font-size", mobile ? 13 : 11.5)
    .text((d) => d.name);

  g.selectAll("text.bv")
    .data(rows)
    .join("text")
    .attr("class", (d) => "bar-value " + cls(d.iso))
    .attr("x", (d) => x(Math.max(0, d.v)) + 6)
    .attr("y", (d) => y(d.iso)! + y.bandwidth() / 2 + 0.5)
    .attr("dy", "0.35em")
    .attr("font-size", mobile ? 11 : 10)
    .text((d) => fmt(d.v));

  const xAxis = d3
    .axisBottom(x)
    .tickValues(tickVals)
    .tickFormat((d) => (d as number).toFixed(1))
    .tickSize(0);
  const xAxisG = g
    .append("g")
    .attr("class", "axis")
    .attr("transform", `translate(0,${innerH})`)
    .call(xAxis);
  xAxisG.select(".domain").remove();
  xAxisG.selectAll("text").attr("dy", 18).attr("font-size", mobile ? 11 : 10);
  void COL.inkFaint;
  void COL.sage;
  void COL.grid;
}
