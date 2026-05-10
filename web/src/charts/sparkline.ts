/**
 * Tiny inline sparkline.
 *
 * Renders into a fluid SVG (no width/height attributes; CSS controls the
 * rendered box, viewBox stretches to fill via preserveAspectRatio="none").
 *
 * Interactive: on mouseover/touch the chart shows a vertical crosshair, a
 * dot at the closest data point, and calls into the shared tooltip with
 * caller-supplied content (e.g. "1995 · z=+0.82").
 */

import * as d3 from "d3";
import { hideTooltip, showTooltip } from "./tooltip";

const SVG_NS = "http://www.w3.org/2000/svg";

export interface SparklineOpts {
  /** Series of values; nulls are skipped on the line, treated as gaps. */
  values: (number | null)[];
  /** Color of the trend line and area fill. */
  color: string;
  /** Optional shared y-domain so multiple sparklines compare visually. */
  yDomain?: [number, number];
  /** ViewBox width — actual rendered width comes from CSS. */
  vbWidth?: number;
  /** ViewBox height — actual rendered height comes from CSS. */
  vbHeight?: number;
  /** Tooltip content as a function of (data index, value at that index). */
  formatTooltip?: (idx: number, v: number) => string;
}

export function sparkline(opts: SparklineOpts): SVGSVGElement {
  const W = opts.vbWidth ?? 200;
  const H = opts.vbHeight ?? 24;
  const pad = 2;

  const svg = document.createElementNS(SVG_NS, "svg") as SVGSVGElement;
  svg.setAttribute("class", "sparkline");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("preserveAspectRatio", "none");

  const present = opts.values
    .map((v, i) => (v == null ? null : { i, v }))
    .filter((p): p is { i: number; v: number } => p != null);
  if (present.length < 2) return svg;

  const xs = d3.scaleLinear().domain([0, opts.values.length - 1]).range([pad, W - pad]);
  const yDomain =
    opts.yDomain ??
    (() => {
      const lo = d3.min(present, (p) => p.v) ?? 0;
      const hi = d3.max(present, (p) => p.v) ?? 1;
      const span = Math.max(0.4, hi - lo);
      return [lo - 0.1 * span, hi + 0.1 * span] as [number, number];
    })();
  const ys = d3.scaleLinear().domain(yDomain).range([H - pad, pad]);

  // Area fill below the line (subtle visual weight).
  const area = d3
    .area<{ i: number; v: number }>()
    .defined((d) => d.v != null)
    .x((d) => xs(d.i))
    .y0(H - pad)
    .y1((d) => ys(d.v))
    .curve(d3.curveMonotoneX);
  const areaPath = document.createElementNS(SVG_NS, "path");
  areaPath.setAttribute("d", area(present) ?? "");
  areaPath.setAttribute("fill", opts.color);
  areaPath.setAttribute("fill-opacity", "0.12");
  svg.appendChild(areaPath);

  // Zero baseline if the y-domain straddles 0.
  if (yDomain[0] < 0 && yDomain[1] > 0) {
    const zero = document.createElementNS(SVG_NS, "line");
    zero.setAttribute("x1", String(pad));
    zero.setAttribute("x2", String(W - pad));
    zero.setAttribute("y1", String(ys(0)));
    zero.setAttribute("y2", String(ys(0)));
    zero.setAttribute("stroke", "rgba(216,220,205,0.18)");
    zero.setAttribute("stroke-width", "0.5");
    zero.setAttribute("vector-effect", "non-scaling-stroke");
    svg.appendChild(zero);
  }

  // Trend line.
  const line = d3
    .line<{ i: number; v: number }>()
    .defined((d) => d.v != null)
    .x((d) => xs(d.i))
    .y((d) => ys(d.v))
    .curve(d3.curveMonotoneX);
  const path = document.createElementNS(SVG_NS, "path");
  path.setAttribute("d", line(present) ?? "");
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", opts.color);
  path.setAttribute("stroke-width", "1.4");
  path.setAttribute("vector-effect", "non-scaling-stroke");
  svg.appendChild(path);

  // Static last-point dot.
  const last = present[present.length - 1];
  const lastDot = document.createElementNS(SVG_NS, "circle");
  lastDot.setAttribute("cx", String(xs(last.i)));
  lastDot.setAttribute("cy", String(ys(last.v)));
  lastDot.setAttribute("r", "1.8");
  lastDot.setAttribute("fill", opts.color);
  lastDot.setAttribute("vector-effect", "non-scaling-stroke");
  svg.appendChild(lastDot);

  // Interactive overlay: cursor line + hover dot + transparent hit rect.
  const overlay = document.createElementNS(SVG_NS, "g");
  overlay.setAttribute("class", "spark-overlay");
  overlay.style.display = "none";
  const cursor = document.createElementNS(SVG_NS, "line");
  cursor.setAttribute("y1", String(pad));
  cursor.setAttribute("y2", String(H - pad));
  cursor.setAttribute("stroke", "rgba(216,220,205,0.6)");
  cursor.setAttribute("stroke-width", "0.6");
  cursor.setAttribute("vector-effect", "non-scaling-stroke");
  overlay.appendChild(cursor);
  const hoverDot = document.createElementNS(SVG_NS, "circle");
  hoverDot.setAttribute("r", "2.6");
  hoverDot.setAttribute("fill", opts.color);
  hoverDot.setAttribute("stroke", "var(--bg-deep)");
  hoverDot.setAttribute("stroke-width", "0.6");
  hoverDot.setAttribute("vector-effect", "non-scaling-stroke");
  overlay.appendChild(hoverDot);
  svg.appendChild(overlay);

  const hit = document.createElementNS(SVG_NS, "rect");
  hit.setAttribute("x", "0");
  hit.setAttribute("y", "0");
  hit.setAttribute("width", String(W));
  hit.setAttribute("height", String(H));
  hit.setAttribute("fill", "transparent");
  hit.style.cursor = "crosshair";
  svg.appendChild(hit);

  let hideTimer: number | null = null;

  const handleAt = (clientX: number): void => {
    const rect = svg.getBoundingClientRect();
    if (rect.width === 0) return;
    const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    const targetIdx = Math.round(ratio * (opts.values.length - 1));
    // Snap to nearest *defined* index.
    let snapped = present[0];
    let bestDist = Infinity;
    for (const p of present) {
      const d = Math.abs(p.i - targetIdx);
      if (d < bestDist) { bestDist = d; snapped = p; }
    }
    overlay.style.display = "";
    cursor.setAttribute("x1", String(xs(snapped.i)));
    cursor.setAttribute("x2", String(xs(snapped.i)));
    hoverDot.setAttribute("cx", String(xs(snapped.i)));
    hoverDot.setAttribute("cy", String(ys(snapped.v)));
    if (opts.formatTooltip) {
      showTooltip(opts.formatTooltip(snapped.i, snapped.v), clientX, rect.top);
    }
  };

  const hide = (): void => {
    overlay.style.display = "none";
    hideTooltip();
  };

  hit.addEventListener("mousemove", (e) => {
    if (hideTimer) { window.clearTimeout(hideTimer); hideTimer = null; }
    handleAt(e.clientX);
  });
  hit.addEventListener("mouseleave", hide);
  hit.addEventListener("touchstart", (e) => {
    if (e.touches.length === 0) return;
    e.preventDefault();
    handleAt(e.touches[0].clientX);
  }, { passive: false });
  hit.addEventListener("touchmove", (e) => {
    if (e.touches.length === 0) return;
    e.preventDefault();
    handleAt(e.touches[0].clientX);
  }, { passive: false });
  hit.addEventListener("touchend", () => {
    if (hideTimer) window.clearTimeout(hideTimer);
    hideTimer = window.setTimeout(hide, 1500);
  });

  return svg;
}
