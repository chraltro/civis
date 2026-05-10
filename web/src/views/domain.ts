/**
 * Domain detail tab.
 *
 * Shows:
 *   - Domain ranking bar (all 29 countries on this domain's z-score)
 *   - Per-indicator block: each indicator's latest rank for A and B,
 *     formatted raw value (e.g. "97%"), z-score, and a sparkline trajectory
 *     for both highlights. Hovering the sparkline shows year + raw value.
 */

import { drawBar } from "../charts/bar";
import { sparkline } from "../charts/sparkline";
import { formatRaw, type CivisData, type IndicatorMeta } from "../data";
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

    const zSeries = data.z[ind.key] ?? {};
    const rawSeries = data.raw?.[ind.key] ?? {};
    const indRanks = rankBy(data, (iso) => zSeries[iso]?.[yi] ?? null);
    const aR = indRanks.get(state.hlA);
    const bR = indRanks.get(state.hlB);
    const aZ = zSeries[state.hlA]?.[yi] ?? null;
    const bZ = zSeries[state.hlB]?.[yi] ?? null;
    const aRaw = rawSeries[state.hlA]?.[yi] ?? null;
    const bRaw = rawSeries[state.hlB]?.[yi] ?? null;

    const aZSeries = zSeries[state.hlA] ?? [];
    const bZSeries = zSeries[state.hlB] ?? [];
    const aRawSeries = rawSeries[state.hlA] ?? [];
    const bRawSeries = rawSeries[state.hlB] ?? [];

    const fmtTip = (label: string, rawArr: (number | null)[], zArr: (number | null)[]) =>
      (i: number) => {
        const yr = data.years[i];
        const raw = rawArr[i];
        const zv = zArr[i];
        const valueDisplay = raw != null ? formatRaw(ind, raw) : "—";
        const zDisplay = zv != null ? `z=${zv >= 0 ? "+" : ""}${zv.toFixed(2)}` : "";
        return `<div class="tt-yr">${yr}</div><div>${label}<span class="tt-v">${valueDisplay}</span></div><div class="tt-z">${zDisplay}</div>`;
      };

    row.innerHTML = `
      <div class="ind-head">
        <span class="ind-label">${ind.label}</span>
        <span class="ind-direction">${ind.direction === "up" ? "higher = better" : "lower = better"}</span>
      </div>
      <div class="ind-rows"></div>
    `;
    const indRowsHost = row.querySelector<HTMLDivElement>(".ind-rows")!;
    indRowsHost.appendChild(
      makeIndRow(
        nameOf[state.hlA], aR, aRaw, aZ, ind, aZSeries, "sage", SAGE, total,
        (i) => fmtTip(nameOf[state.hlA], aRawSeries, aZSeries)(i),
      ),
    );
    indRowsHost.appendChild(
      makeIndRow(
        nameOf[state.hlB], bR, bRaw, bZ, ind, bZSeries, "amber", AMBER, total,
        (i) => fmtTip(nameOf[state.hlB], bRawSeries, bZSeries)(i),
      ),
    );

    rowsHost.appendChild(row);
  }
}

function makeIndRow(
  name: string,
  rank: number | undefined,
  raw: number | null,
  z: number | null,
  meta: IndicatorMeta,
  zSeriesForSpark: (number | null)[],
  cls: "sage" | "amber",
  color: string,
  total: number,
  formatTooltip: (i: number) => string,
): HTMLElement {
  const row = document.createElement("div");
  row.className = `ind-row ${cls}`;
  const spark = sparkline({
    values: zSeriesForSpark,
    color,
    formatTooltip: (i) => formatTooltip(i),
  });
  row.innerHTML = `
    <span class="ir-name">${name}</span>
    <span class="ir-value">${raw == null ? "—" : formatRaw(meta, raw)}</span>
    <span class="ir-rank">${rank ? ordinal(rank) : "—"} <span class="ir-of">of ${total}</span></span>
    <span class="ir-z">z=${zfmt(z)}</span>
  `;
  const sparkWrap = document.createElement("span");
  sparkWrap.className = "ir-spark";
  sparkWrap.appendChild(spark);
  row.insertBefore(sparkWrap, row.querySelector(".ir-z"));
  return row;
}
