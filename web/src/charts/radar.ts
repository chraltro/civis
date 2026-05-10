/**
 * Radar chart: A vs B across all 9 domain z-means at the latest year, with
 * the panel median drawn as a dashed reference.
 */

import * as d3 from "d3";
import type { CivisData } from "../data";
import type { CompositeContext } from "../state";
import { state } from "../state";

const COL = { inkFaint: "#6e7869" };

function isMobile(): boolean {
  return window.innerWidth < 600;
}

export function drawRadar(data: CivisData, ctx: CompositeContext): void {
  const svg = d3.select<SVGSVGElement, unknown>("#radar");
  svg.selectAll("*").remove();
  const mobile = isMobile();
  const W = mobile ? 480 : 720;
  const H = mobile ? 480 : 540;
  svg.attr("viewBox", `0 0 ${W} ${H}`);

  const cx = W / 2;
  const cy = H / 2 + 8;
  const R = Math.min(W, H) * (mobile ? 0.32 : 0.36);

  const yi = data.years.indexOf(Math.max(...data.years));
  const aVals = data.domains.map((d) => data.domain_z[d]?.[state.hlA]?.[yi] ?? 0);
  const bVals = data.domains.map((d) => data.domain_z[d]?.[state.hlB]?.[yi] ?? 0);

  const medians = data.domains.map((d) => {
    const xs = data.countries
      .map((c) => data.domain_z[d]?.[c.iso]?.[yi])
      .filter((v): v is number => v != null)
      .sort((p, q) => p - q);
    return xs.length ? xs[Math.floor(xs.length / 2)] : 0;
  });

  const zToR = (z: number): number => {
    const t = (z + 2.5) / 5;
    return Math.max(0, Math.min(R, t * R));
  };
  const angleFor = (i: number): number =>
    -Math.PI / 2 + (i / data.domains.length) * 2 * Math.PI;

  const gridZs = [-2, -1, 0, 1, 2];
  for (const z of gridZs) {
    svg
      .append("circle")
      .attr("class", "radar-grid" + (z === 0 ? " zero" : ""))
      .attr("cx", cx)
      .attr("cy", cy)
      .attr("r", zToR(z));
  }

  data.domains.forEach((_d, i) => {
    const a = angleFor(i);
    svg
      .append("line")
      .attr("class", "radar-grid")
      .attr("x1", cx)
      .attr("y1", cy)
      .attr("x2", cx + Math.cos(a) * R)
      .attr("y2", cy + Math.sin(a) * R);
  });

  const medianPath = medians
    .map((z, i) => {
      const a = angleFor(i);
      const r = zToR(z);
      return `${cx + Math.cos(a) * r},${cy + Math.sin(a) * r}`;
    })
    .join(" ");
  svg.append("polygon").attr("class", "radar-poly median").attr("points", medianPath);

  const drawPoly = (vals: number[], cls: "a" | "b") => {
    const pts = vals.map((z, i) => {
      const a = angleFor(i);
      const r = zToR(z);
      return [cx + Math.cos(a) * r, cy + Math.sin(a) * r] as const;
    });
    svg
      .append("polygon")
      .attr("class", "radar-poly " + cls)
      .attr("points", pts.map((p) => p.join(",")).join(" "));
    for (const [px, py] of pts) {
      svg
        .append("circle")
        .attr("class", "radar-dot " + cls)
        .attr("cx", px)
        .attr("cy", py)
        .attr("r", mobile ? 3 : 2.5);
    }
  };
  drawPoly(aVals, "a");
  drawPoly(bVals, "b");

  data.domains.forEach((d, i) => {
    const a = angleFor(i);
    const lr = R + (mobile ? 16 : 28);
    const lx = cx + Math.cos(a) * lr;
    const ly = cy + Math.sin(a) * lr;
    let anchor: "start" | "end" | "middle" = "middle";
    if (Math.abs(Math.cos(a)) > 0.3) anchor = Math.cos(a) > 0 ? "start" : "end";
    svg
      .append("text")
      .attr("class", "radar-axis-label")
      .attr("x", lx)
      .attr("y", ly)
      .attr("text-anchor", anchor)
      .attr("dominant-baseline", "middle")
      .attr("font-size", mobile ? 10 : 12)
      .text(d);
  });

  for (const z of gridZs) {
    if (z === 2 || z === -2) continue;
    svg
      .append("text")
      .attr("class", "radar-axis-label")
      .attr("x", cx + 4)
      .attr("y", cy - zToR(z))
      .attr("font-size", 9)
      .attr("fill", COL.inkFaint)
      .text((z >= 0 ? "+" : "") + z);
  }

  const nameOf = Object.fromEntries(data.countries.map((c) => [c.iso, c.name]));
  const titleEl = document.getElementById("radar-title");
  if (titleEl) {
    titleEl.innerHTML = `<span style="color:var(--sage)">${nameOf[state.hlA]}</span> vs <span style="color:var(--amber)">${nameOf[state.hlB]}</span>`;
  }
  const aEl = document.getElementById("radar-score-a");
  const bEl = document.getElementById("radar-score-b");
  if (aEl) {
    const v = ctx.latest[state.hlA];
    aEl.textContent = v == null ? "—" : `${nameOf[state.hlA]} ${v >= 0 ? "+" : ""}${v.toFixed(2)}`;
  }
  if (bEl) {
    const v = ctx.latest[state.hlB];
    bEl.textContent = v == null ? "—" : `${nameOf[state.hlB]} ${v >= 0 ? "+" : ""}${v.toFixed(2)}`;
  }
}
