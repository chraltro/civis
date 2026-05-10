/** "About" panel — methodology in compact prose. */

import type { CivisData } from "../data";

export function buildAboutPanel(data: CivisData): void {
  const host = document.getElementById("about-panel");
  if (!host) return;
  const inds = (domain: string): string =>
    data.indicators
      .filter((i) => i.domain === domain)
      .map((i) => i.label)
      .join(", ");
  host.innerHTML = `
    <p class="lead">
      A response to the BCW Index, which ranked Hong Kong second by counting
      "rich" six times across twelve indicators and ignoring inequality, freedom,
      and sustainability. Civis aggregates ${data.indicators.length} indicators
      hierarchically across nine equally-weighted domains. Adjust the weights
      to disagree.
    </p>
    <ul class="domain-table">
      ${data.domains.map((d) => `
        <li><span class="domain-name">${d}</span><span class="domain-inds">${inds(d)}</span></li>
      `).join("")}
    </ul>
    <p class="fine">
      Each indicator is z-scored across the full panel of 29 countries × 1990 onwards,
      winsorized at ±2.5σ, sign-flipped where lower is better. Domain score = unweighted
      mean of indicator z-scores within the domain. Country score = weighted mean of
      domain scores (default weights are equal). Sporadic series are linearly
      interpolated and held constant before the first and after the last observation.
    </p>
    <p class="fine src-row">
      Sources: World Bank WDI · OWID Cantril Ladder · V-Dem ·
      RSF · Transparency International · UNDP · OECD · Gallup. CC-BY 4.0.
    </p>
  `;
}
