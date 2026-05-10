/**
 * Tiny inline sparkline (~80x18). Used for indicator trajectories in the
 * domain detail view.
 */

import * as d3 from "d3";

export interface SparklineOpts {
  /** Series of values; nulls are skipped. */
  values: (number | null)[];
  /** Color of the trend line. */
  color: string;
  /** Optional shared y-domain so multiple sparklines compare visually. */
  yDomain?: [number, number];
  width?: number;
  height?: number;
}

export function sparkline(opts: SparklineOpts): SVGSVGElement {
  const W = opts.width ?? 88;
  const H = opts.height ?? 22;
  const pad = 2;

  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg") as SVGSVGElement;
  svg.setAttribute("class", "sparkline");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("width", String(W));
  svg.setAttribute("height", String(H));

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
      return [lo - 0.05 * Math.abs(hi - lo + 1e-9), hi + 0.05 * Math.abs(hi - lo + 1e-9)] as [
        number,
        number,
      ];
    })();
  const ys = d3.scaleLinear().domain(yDomain).range([H - pad, pad]);

  const line = d3
    .line<{ i: number; v: number }>()
    .defined((d) => d.v != null)
    .x((d) => xs(d.i))
    .y((d) => ys(d.v))
    .curve(d3.curveMonotoneX);

  // baseline at y=0 if in range
  if (yDomain[0] < 0 && yDomain[1] > 0) {
    const zero = document.createElementNS(ns, "line");
    zero.setAttribute("x1", String(pad));
    zero.setAttribute("x2", String(W - pad));
    zero.setAttribute("y1", String(ys(0)));
    zero.setAttribute("y2", String(ys(0)));
    zero.setAttribute("stroke", "rgba(216,220,205,0.18)");
    zero.setAttribute("stroke-width", "0.5");
    svg.appendChild(zero);
  }

  const path = document.createElementNS(ns, "path");
  path.setAttribute("d", line(present) ?? "");
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", opts.color);
  path.setAttribute("stroke-width", "1.4");
  svg.appendChild(path);

  // last-point dot
  const last = present[present.length - 1];
  const dot = document.createElementNS(ns, "circle");
  dot.setAttribute("cx", String(xs(last.i)));
  dot.setAttribute("cy", String(ys(last.v)));
  dot.setAttribute("r", "1.8");
  dot.setAttribute("fill", opts.color);
  svg.appendChild(dot);

  return svg;
}
