/** Overview tab: composite ranking + radar + composite trajectory. */

import { drawBar } from "../charts/bar";
import { drawRadar } from "../charts/radar";
import { drawTimeSeries } from "../charts/timeseries";
import type { CivisData } from "../data";
import { computeComposite, state } from "../state";

export function renderOverview(host: HTMLElement, data: CivisData): void {
  host.innerHTML = `
    <div class="overview-grid">
      <section class="card">
        <h2>Ranking</h2>
        <p class="card-sub">Composite score, latest year</p>
        <svg id="bar" class="chart" viewBox="0 0 720 640" preserveAspectRatio="xMidYMid meet"></svg>
      </section>
      <section class="card">
        <h2>Domain shape</h2>
        <p class="card-sub">
          <span class="hl" id="radar-title"></span>
          <span class="scores"><span class="sage" id="radar-score-a"></span> vs <span class="amber" id="radar-score-b"></span></span>
        </p>
        <svg id="radar" class="chart" viewBox="0 0 720 540" preserveAspectRatio="xMidYMid meet"></svg>
      </section>
      <section class="card span-2">
        <h2>Trajectory</h2>
        <p class="card-sub">Composite z-score over time, all 29 economies</p>
        <svg id="ts" class="chart" viewBox="0 0 1320 540" preserveAspectRatio="xMidYMid meet"></svg>
      </section>
    </div>
  `;

  const ctx = computeComposite(data);
  drawBar({
    selector: "#bar",
    data,
    valueOf: (iso) => ctx.latest[iso] ?? null,
  });
  drawRadar(data, ctx);
  drawTimeSeries(data, ctx);

  // The radar's title uses A/B names so set it
  const nameOf = Object.fromEntries(data.countries.map((c) => [c.iso, c.name]));
  const titleEl = document.getElementById("radar-title");
  if (titleEl) {
    titleEl.innerHTML = `<span class="sage">${nameOf[state.hlA]}</span> · <span class="amber">${nameOf[state.hlB]}</span>`;
  }
}
