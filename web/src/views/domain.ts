/**
 * Domain detail tab.
 *
 * Shows:
 *   - Domain ranking bar (all 29 countries on this domain's z-score)
 *   - Per-indicator block: each indicator's latest rank for A and B,
 *     z-score for A and B, plus a sparkline trajectory each.
 */

import { drawBar } from "../charts/bar";
import { sparkline } from "../charts/sparkline";
import type { CivisData } from "../data";
import { rankBy, state } from "../state";

const SAGE = "#94b09e";
const AMBER = "#d2965a";

const DOMAIN_TAGLINES: Record<string, string> = {
  Material: "GDP, household consumption, health spending, broadband.",
  Health: "Life expectancy, mortality, healthy life years.",
  Knowledge: "Schooling, tertiary attainment, internet access, R&D.",
  Safety: "Homicide, suicide, road traffic deaths.",
  Equality: "Income Gini, gender development, top-10% income share.",
  Freedom: "Liberal democracy, press freedom, anti-corruption, civil liberties.",
  Work: "Working hours, unemployment, employment-to-population.",
  Environment: "PM2.5, CO₂ per capita, renewables, protected land.",
  Wellbeing: "Cantril ladder, adolescent fertility, positive affect.",
};

function ordinal(n: number): string {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return `${n}${s[(v - 20) % 10] ?? s[v] ?? s[0]}`;
}

function zfmt(z: number | null): string {
  if (z == null) return "—";
  return (z >= 0 ? "+" : "") + z.toFixed(2);
}

export function renderDomain(host: HTMLElement, data: CivisData, domain: string): void {
  const yi = data.years.indexOf(Math.max(...data.years));
  const inds = data.indicators.filter((i) => i.domain === domain);
  const nameOf = Object.fromEntries(data.countries.map((c) => [c.iso, c.name]));

  // Domain rank
  const domainRanks = rankBy(data, (iso) => data.domain_z[domain]?.[iso]?.[yi] ?? null);
  const aRank = domainRanks.get(state.hlA);
  const bRank = domainRanks.get(state.hlB);
  const total = data.countries.length;

  host.innerHTML = `
    <section class="domain-head">
      <h2>${domain}</h2>
      <p class="card-sub">${DOMAIN_TAGLINES[domain] ?? ""}</p>
      <div class="domain-rank-chips">
        <span class="chip sage">${nameOf[state.hlA]}: ${aRank ? ordinal(aRank) : "—"} of ${total}</span>
        <span class="chip amber">${nameOf[state.hlB]}: ${bRank ? ordinal(bRank) : "—"} of ${total}</span>
      </div>
    </section>
    <section class="card">
      <h3>Domain score</h3>
      <p class="card-sub">All 29 economies, z-score on ${domain}</p>
      <svg id="domain-bar" class="chart" viewBox="0 0 720 640" preserveAspectRatio="xMidYMid meet"></svg>
    </section>
    <section class="indicator-list">
      <h3>Indicators (${inds.length})</h3>
      <div class="indicator-rows" id="indicator-rows"></div>
    </section>
  `;

  drawBar({
    selector: "#domain-bar",
    data,
    valueOf: (iso) => data.domain_z[domain]?.[iso]?.[yi] ?? null,
  });

  const rowsHost = document.getElementById("indicator-rows")!;
  for (const ind of inds) {
    const row = document.createElement("div");
    row.className = "indicator-row";

    // Compute rank within this indicator's z-scores
    const zSeries = data.z[ind.key] ?? {};
    const indRanks = rankBy(data, (iso) => zSeries[iso]?.[yi] ?? null);
    const aR = indRanks.get(state.hlA);
    const bR = indRanks.get(state.hlB);
    const aZ = zSeries[state.hlA]?.[yi] ?? null;
    const bZ = zSeries[state.hlB]?.[yi] ?? null;

    const aSeries = zSeries[state.hlA] ?? [];
    const bSeries = zSeries[state.hlB] ?? [];

    const fmtTip = (label: string) => (i: number, v: number) =>
      `<span class="tt-yr">${data.years[i]}</span> · ${label} · z=${v >= 0 ? "+" : ""}${v.toFixed(2)}`;

    row.innerHTML = `
      <div class="ind-head">
        <span class="ind-label">${ind.label}</span>
        <span class="ind-direction">${ind.direction === "up" ? "higher = better" : "lower = better"}</span>
      </div>
      <div class="ind-rows"></div>
    `;
    const indRowsHost = row.querySelector<HTMLDivElement>(".ind-rows")!;
    indRowsHost.appendChild(makeIndRow(nameOf[state.hlA], aR, aZ, aSeries, "sage", SAGE, total, fmtTip(nameOf[state.hlA])));
    indRowsHost.appendChild(makeIndRow(nameOf[state.hlB], bR, bZ, bSeries, "amber", AMBER, total, fmtTip(nameOf[state.hlB])));

    rowsHost.appendChild(row);
  }
}

function makeIndRow(
  name: string,
  rank: number | undefined,
  z: number | null,
  series: (number | null)[],
  cls: "sage" | "amber",
  color: string,
  total: number,
  formatTooltip: (i: number, v: number) => string,
): HTMLElement {
  const row = document.createElement("div");
  row.className = `ind-row ${cls}`;
  const spark = sparkline({ values: series, color, formatTooltip });
  row.innerHTML = `
    <span class="ir-name">${name}</span>
    <span class="ir-rank">${rank ? ordinal(rank) : "—"} <span class="ir-of">of ${total}</span></span>
    <span class="ir-z">z=${zfmt(z)}</span>
  `;
  const sparkWrap = document.createElement("span");
  sparkWrap.className = "ir-spark";
  sparkWrap.appendChild(spark);
  row.insertBefore(sparkWrap, row.querySelector(".ir-z"));
  return row;
}
