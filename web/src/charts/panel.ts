/**
 * Domain panels: nine small-multiple line charts, one per domain.
 */

import * as d3 from "d3";
import type { CivisData } from "../data";
import { state } from "../state";

const COL = { grid: "#2a3a32" };

function isMobile(): boolean {
  return window.innerWidth < 600;
}

function domainPanel(parent: HTMLElement, data: CivisData, domain: string): void {
  const wrap = document.createElement("div");
  wrap.className = "small-panel";
  parent.appendChild(wrap);

  const title = document.createElement("div");
  title.className = "small-title";
  title.textContent = domain;
  wrap.appendChild(title);

  const inds = data.indicators.filter((i) => i.domain === domain).map((i) => i.label);
  const sub = document.createElement("div");
  sub.className = "small-sub";
  sub.textContent = inds.join(" · ");
  wrap.appendChild(sub);

  const mobile = isMobile();
  const W = 380;
  const H = mobile ? 220 : 200;
  const margin = mobile
    ? { top: 14, right: 40, bottom: 26, left: 38 }
    : { top: 14, right: 40, bottom: 24, left: 38 };
  const innerW = W - margin.left - margin.right;
  const innerH = H - margin.top - margin.bottom;

  const svg = d3
    .select(wrap)
    .append("svg")
    .attr("class", "chart")
    .attr("viewBox", `0 0 ${W} ${H}`)
    .attr("preserveAspectRatio", "xMidYMid meet");
  const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);

  const allVals: number[] = [];
  for (const c of data.countries) {
    for (const v of data.domain_z[domain]?.[c.iso] ?? []) if (v != null) allVals.push(v);
  }
  if (allVals.length === 0) return;
  const yMin = Math.floor((d3.min(allVals) ?? -1) * 2) / 2;
  const yMax = Math.ceil((d3.max(allVals) ?? 1) * 2) / 2;
  const x = d3.scaleLinear().domain([data.years[0], data.years[data.years.length - 1] + 2]).range([0, innerW]);
  const y = d3.scaleLinear().domain([yMin, yMax]).range([innerH, 0]).nice();

  g.append("g")
    .attr("class", "grid")
    .selectAll("line.h")
    .data(y.ticks(4))
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
    .attr("y2", y(0))
    .attr("stroke-opacity", 0.5);

  type Pt = { year: number; v: number | null };
  const line = d3
    .line<Pt>()
    .defined((d) => d.v != null)
    .x((d) => x(d.year))
    .y((d) => y(d.v as number))
    .curve(d3.curveMonotoneX);

  const bgStroke = mobile ? 0.7 : 0.5;
  const hlStroke = mobile ? 2 : 1.6;

  const seriesFor = (iso: string): Pt[] =>
    (data.domain_z[domain]?.[iso] ?? []).map((v, i) => ({ year: data.years[i], v }));

  for (const c of data.countries) {
    if (c.iso === state.hlA || c.iso === state.hlB) continue;
    g.append("path")
      .datum(seriesFor(c.iso))
      .attr("class", "small-line")
      .attr("stroke-width", bgStroke)
      .attr("d", line);
  }
  for (const [cls, iso] of [
    ["hl-a", state.hlA],
    ["hl-b", state.hlB],
  ] as const) {
    g.append("path")
      .datum(seriesFor(iso))
      .attr("class", "small-line " + cls)
      .attr("stroke-width", hlStroke)
      .attr("d", line);
  }

  const xTicks = [1990, 2000, 2010, 2020];
  const xAxis = d3
    .axisBottom(x)
    .tickValues(xTicks)
    .tickFormat(d3.format("d") as (v: d3.NumberValue) => string)
    .tickSize(-innerH);
  const xg = g
    .append("g")
    .attr("class", "axis")
    .attr("transform", `translate(0,${innerH})`)
    .call(xAxis);
  xg.select(".domain").remove();
  xg.selectAll("line").attr("stroke", COL.grid).attr("stroke-width", 0.4);
  xg.selectAll("text").attr("font-size", mobile ? 10 : 9).attr("dy", 12);

  const yAxis = d3
    .axisLeft(y)
    .ticks(4)
    .tickSize(-innerW)
    .tickFormat((d) => (d as number).toFixed(1));
  const yg = g.append("g").attr("class", "axis").call(yAxis);
  yg.select(".domain").remove();
  yg.selectAll("line").attr("stroke", COL.grid).attr("stroke-width", 0.4);
  yg.selectAll("text").attr("font-size", mobile ? 10 : 9);

  type EndLabel = { iso: string; cls: string; x: number; y: number; text: string };
  const endLabel = (iso: string, cls: string): EndLabel | null => {
    const series = data.domain_z[domain]?.[iso] ?? [];
    let lastIdx = series.length - 1;
    while (lastIdx >= 0 && series[lastIdx] == null) lastIdx--;
    if (lastIdx < 0) return null;
    const v = series[lastIdx]!;
    return {
      iso,
      cls,
      x: x(data.years[lastIdx]) + 4,
      y: y(v),
      text: (v >= 0 ? "+" : "") + v.toFixed(1),
    };
  };
  const labels = [endLabel(state.hlA, "small-end-a"), endLabel(state.hlB, "small-end-b")].filter(
    (l): l is EndLabel => l != null,
  );
  if (labels.length === 2) {
    const dy = Math.abs(labels[0].y - labels[1].y);
    if (dy < 11) {
      const sign = labels[0].y < labels[1].y ? -1 : 1;
      const mid = (labels[0].y + labels[1].y) / 2;
      labels[0].y = mid + sign * 6;
      labels[1].y = mid - sign * 6;
    }
  }
  for (const L of labels) {
    g.append("text")
      .attr("class", L.cls)
      .attr("x", L.x)
      .attr("y", L.y)
      .attr("font-size", mobile ? 10.5 : 9)
      .text(L.text);
  }
}

export function drawPanels(data: CivisData): void {
  const host = document.getElementById("panels");
  if (!host) return;
  host.innerHTML = "";
  for (const d of data.domains) domainPanel(host, data, d);
}
