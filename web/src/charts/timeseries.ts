/**
 * Composite z-score time series. Used in the Overview tab.
 */

import * as d3 from "d3";
import type { CivisData } from "../data";
import type { CompositeContext } from "../state";
import { state } from "../state";
import { hideTooltip, showTooltip } from "./tooltip";

const COL = { grid: "#2a3a32", sage: "#94b09e", amber: "#d2965a" };

function isMobile(): boolean {
  return window.innerWidth < 600;
}

export function drawTimeSeries(data: CivisData, ctx: CompositeContext): void {
  const svg = d3.select<SVGSVGElement, unknown>("#ts");
  svg.selectAll("*").remove();

  const mobile = isMobile();
  const W = mobile ? 600 : 1320;
  const H = mobile ? 480 : 540;
  const margin = mobile
    ? { top: 6, right: 130, bottom: 32, left: 38 }
    : { top: 6, right: 130, bottom: 38, left: 50 };
  const innerW = W - margin.left - margin.right;
  const innerH = H - margin.top - margin.bottom;
  svg.attr("viewBox", `0 0 ${W} ${H}`);
  const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);

  const yearMin = data.years[0];
  const yearMax = data.years[data.years.length - 1] + 2;
  const x = d3.scaleLinear().domain([yearMin, yearMax]).range([0, innerW]);
  const allVals: number[] = [];
  for (const c of data.countries) {
    for (const v of ctx.composite[c.iso]) if (v != null) allVals.push(v);
  }
  const yDom: [number, number] = [
    Math.floor((d3.min(allVals) ?? -1) * 2) / 2,
    Math.ceil((d3.max(allVals) ?? 1) * 2) / 2,
  ];
  const y = d3.scaleLinear().domain(yDom).range([innerH, 0]).nice();

  g.append("g")
    .attr("class", "grid")
    .selectAll("line.h")
    .data(y.ticks(7))
    .join("line")
    .attr("class", "h")
    .attr("x1", 0)
    .attr("x2", innerW)
    .attr("y1", (d) => y(d))
    .attr("y2", (d) => y(d));

  g.append("line")
    .attr("class", "baseline")
    .attr("x1", 0)
    .attr("x2", innerW)
    .attr("y1", y(0))
    .attr("y2", y(0));

  type Pt = { year: number; v: number | null };
  const line = d3
    .line<Pt>()
    .defined((d) => d.v != null)
    .x((d) => x(d.year))
    .y((d) => y(d.v as number))
    .curve(d3.curveMonotoneX);

  const seriesFor = (iso: string): Pt[] =>
    ctx.composite[iso].map((v, i) => ({ year: data.years[i], v }));

  for (const c of data.countries) {
    if (c.iso === state.hlA || c.iso === state.hlB) continue;
    g.append("path")
      .datum(seriesFor(c.iso))
      .attr("class", "ts-line")
      .attr("stroke-width", mobile ? 0.9 : 0.5)
      .attr("d", line);
  }

  for (const [cls, iso] of [
    ["hl-a", state.hlA],
    ["hl-b", state.hlB],
  ] as const) {
    g.append("path")
      .datum(seriesFor(iso))
      .attr("class", "ts-line " + cls)
      .attr("stroke-width", mobile ? 2.6 : 2)
      .attr("d", line);
  }

  const xTickVals = mobile
    ? [1990, 2000, 2010, 2020]
    : [1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025];
  const xAxis = d3
    .axisBottom(x)
    .tickValues(xTickVals)
    .tickFormat(d3.format("d") as (v: d3.NumberValue) => string)
    .tickSize(-innerH);
  const yAxis = d3
    .axisLeft(y)
    .ticks(mobile ? 5 : 7)
    .tickSize(-innerW)
    .tickFormat((d) => (d as number).toFixed(1));

  const xg = g
    .append("g")
    .attr("class", "axis")
    .attr("transform", `translate(0,${innerH})`)
    .call(xAxis);
  xg.select(".domain").remove();
  xg.selectAll("line").attr("stroke", COL.grid).attr("stroke-width", 0.4);
  xg.selectAll("text").attr("dy", 14).attr("font-size", mobile ? 12 : 10);

  const yg = g.append("g").attr("class", "axis").call(yAxis);
  yg.select(".domain").remove();
  yg.selectAll("line").attr("stroke", COL.grid).attr("stroke-width", 0.4);
  yg.selectAll("text").attr("font-size", mobile ? 12 : 10);

  // Compact end-labels for A / B only
  const nameOf = Object.fromEntries(data.countries.map((c) => [c.iso, c.name]));
  for (const [cls, iso] of [
    ["hl-a", state.hlA],
    ["hl-b", state.hlB],
  ] as const) {
    const v = ctx.latest[iso];
    if (v == null) continue;
    g.append("text")
      .attr("class", "ts-end-label " + cls)
      .attr("x", innerW + 8)
      .attr("y", y(v))
      .attr("font-size", mobile ? 11 : 9.5)
      .text(`${nameOf[iso]}  ${v >= 0 ? "+" : ""}${v.toFixed(2)}`);
  }

  // Hover crosshair + tooltip showing year and both highlight values.
  const overlay = g.append("g").attr("class", "ts-overlay").style("display", "none");
  const cursor = overlay
    .append("line")
    .attr("class", "ts-cursor")
    .attr("y1", 0)
    .attr("y2", innerH)
    .attr("stroke", "rgba(216,220,205,0.5)")
    .attr("stroke-width", 0.6);
  const dotA = overlay
    .append("circle")
    .attr("r", 3.4)
    .attr("fill", COL.sage)
    .attr("stroke", "var(--bg)")
    .attr("stroke-width", 1);
  const dotB = overlay
    .append("circle")
    .attr("r", 3.4)
    .attr("fill", COL.amber)
    .attr("stroke", "var(--bg)")
    .attr("stroke-width", 1);

  const hit = g
    .append("rect")
    .attr("x", 0)
    .attr("y", 0)
    .attr("width", innerW)
    .attr("height", innerH)
    .attr("fill", "transparent")
    .style("cursor", "crosshair");

  let hideTimer: number | null = null;

  const handleAt = (clientX: number, clientY: number): void => {
    const node = (svg.node() as SVGSVGElement) ?? null;
    if (!node) return;
    const rect = node.getBoundingClientRect();
    const ratio = (clientX - rect.left) / rect.width;
    const yearSpan = data.years.length - 1;
    const fracInChart = (ratio * W - margin.left) / innerW;
    const yearFrac = Math.max(0, Math.min(1, fracInChart));
    const idx = Math.round(yearFrac * yearSpan);
    const year = data.years[idx];
    const va = ctx.composite[state.hlA]?.[idx] ?? null;
    const vb = ctx.composite[state.hlB]?.[idx] ?? null;
    overlay.style("display", null);
    cursor.attr("x1", x(year)).attr("x2", x(year));
    if (va != null) dotA.attr("cx", x(year)).attr("cy", y(va)).style("display", null);
    else dotA.style("display", "none");
    if (vb != null) dotB.attr("cx", x(year)).attr("cy", y(vb)).style("display", null);
    else dotB.style("display", "none");

    const fmt = (v: number | null) => (v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}`);
    showTooltip(
      `<div class="tt-yr">${year}</div>` +
        `<div><span class="tt-dot sage"></span>${nameOf[state.hlA]}<span class="tt-v">${fmt(va)}</span></div>` +
        `<div><span class="tt-dot amber"></span>${nameOf[state.hlB]}<span class="tt-v">${fmt(vb)}</span></div>`,
      clientX,
      clientY,
    );
  };

  const hide = (): void => {
    overlay.style("display", "none");
    hideTooltip();
  };

  hit.on("mousemove", (e) => {
    if (hideTimer) { window.clearTimeout(hideTimer); hideTimer = null; }
    handleAt(e.clientX, e.clientY);
  });
  hit.on("mouseleave", hide);
  hit.on("touchstart", (e) => {
    if (e.touches.length === 0) return;
    e.preventDefault();
    handleAt(e.touches[0].clientX, e.touches[0].clientY);
  });
  hit.on("touchmove", (e) => {
    if (e.touches.length === 0) return;
    e.preventDefault();
    handleAt(e.touches[0].clientX, e.touches[0].clientY);
  });
  hit.on("touchend", () => {
    if (hideTimer) window.clearTimeout(hideTimer);
    hideTimer = window.setTimeout(hide, 1500);
  });
}
