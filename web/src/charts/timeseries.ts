/**
 * Time series chart: composite over years for all 29 countries with named highlights.
 */

import * as d3 from "d3";
import type { CivisData } from "../data";
import type { CompositeContext } from "../state";
import { state } from "../state";

const COL = { grid: "#2a3a32" };

function isMobile(): boolean {
  return window.innerWidth < 600;
}

export function drawTimeSeries(data: CivisData, ctx: CompositeContext): void {
  const svg = d3.select<SVGSVGElement, unknown>("#ts");
  svg.selectAll("*").remove();

  const mobile = isMobile();
  const W = mobile ? 600 : 1320;
  const H = mobile ? 540 : 640;
  const margin = mobile
    ? { top: 6, right: 130, bottom: 36, left: 38 }
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

  const bgStroke = mobile ? 0.9 : 0.5;
  const namedStroke = mobile ? 1.1 : 0.8;
  const hlStroke = mobile ? 2.6 : 2;

  const seriesFor = (iso: string): Pt[] =>
    ctx.composite[iso].map((v, i) => ({ year: data.years[i], v }));

  for (const c of data.countries) {
    if (c.iso === state.hlA || c.iso === state.hlB) continue;
    g.append("path")
      .datum(seriesFor(c.iso))
      .attr("class", "ts-line")
      .attr("stroke-width", bgStroke)
      .attr("d", line);
  }

  const NAMED_BASE = ["NOR", "ISL", "SWE", "CHE", "SGP", "ESP", "PRT", "JPN", "GBR", "FRA", "LTU"];
  const NAMED = NAMED_BASE.filter((i) => i !== state.hlA && i !== state.hlB);
  const namedToDraw = mobile ? NAMED.filter((i) => ["NOR", "ISL", "SGP", "LTU"].includes(i)) : NAMED;
  for (const iso of namedToDraw) {
    g.append("path")
      .datum(seriesFor(iso))
      .attr("class", "ts-line named")
      .attr("stroke-width", namedStroke)
      .attr("d", line);
  }

  for (const [cls, iso] of [
    ["hl-a", state.hlA],
    ["hl-b", state.hlB],
  ] as const) {
    g.append("path")
      .datum(seriesFor(iso))
      .attr("class", "ts-line " + cls)
      .attr("stroke-width", hlStroke)
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

  if (!mobile) {
    g.append("text")
      .attr("class", "axis-label")
      .attr("transform", `translate(-36, ${innerH / 2}) rotate(-90)`)
      .attr("text-anchor", "middle")
      .text("Civis composite z-score");
  }

  const nameOf = Object.fromEntries(data.countries.map((c) => [c.iso, c.name]));
  const endIsosBase = ["NOR", "ISL", "SWE", "CHE", "SGP", "ESP", "PRT", "JPN", "GBR", "FRA", "LTU"];
  const endIsosMobile = ["NOR", "ISL", "LTU"];
  const endIsos = Array.from(
    new Set([...(mobile ? endIsosMobile : endIsosBase), state.hlA, state.hlB]),
  );

  type LD = { iso: string; cls: string; name: string; v: number; yPos: number };
  const labelData: LD[] = endIsos
    .filter((iso) => ctx.latest[iso] != null)
    .map((iso) => ({
      iso,
      cls: iso === state.hlA ? "hl-a" : iso === state.hlB ? "hl-b" : "",
      name: nameOf[iso],
      v: ctx.latest[iso],
      yPos: y(ctx.latest[iso]),
    }))
    .sort((a, b) => a.yPos - b.yPos);

  const minGap = mobile ? 16 : 14;
  for (let pass = 0; pass < 80; pass++) {
    let moved = false;
    for (let i = 1; i < labelData.length; i++) {
      const dy = labelData[i].yPos - labelData[i - 1].yPos;
      if (dy < minGap) {
        const push = (minGap - dy) / 2;
        labelData[i - 1].yPos -= push;
        labelData[i].yPos += push;
        moved = true;
      }
    }
    if (!moved) break;
  }

  for (const d of labelData) {
    g.append("text")
      .attr("class", "ts-end-label " + d.cls)
      .attr("x", innerW + 8)
      .attr("y", d.yPos)
      .attr("font-size", mobile ? 11 : 9.5)
      .text(`${d.name}  ${d.v >= 0 ? "+" : ""}${d.v.toFixed(2)}`);
  }
}
