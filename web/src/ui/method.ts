/**
 * Methodology accordion + indicators-by-domain list.
 */

import type { CivisData } from "../data";

export function buildMethod(data: CivisData): void {
  const list = document.getElementById("domains-list");
  if (list) {
    list.innerHTML = "";
    for (const d of data.domains) {
      const inds = data.indicators
        .filter((i) => i.domain === d)
        .map((i) => i.label)
        .join(", ");
      const li = document.createElement("li");
      li.innerHTML = `<span class="domain-name">${d}</span> · ${inds}`;
      list.appendChild(li);
    }
  }
  const btn = document.getElementById("method-toggle");
  const detail = document.getElementById("method-detail");
  if (btn && detail) {
    btn.addEventListener("click", () => {
      const open = detail.classList.toggle("open");
      btn.textContent = (open ? "▾" : "▸") + " How this differs from the BCW Index";
    });
  }
}

export function buildFooter(data: CivisData): void {
  const f = document.getElementById("country-list-footnote");
  if (f) {
    const names = data.countries.map((c) => c.name).join(" · ");
    f.innerHTML = `${data.countries.length} economies — ${names}. Each indicator is z-scored across the full panel of ${data.countries.length} countries × ${data.years[0]}–${data.years[data.years.length - 1]}, winsorized at ±2.5σ, and sign-flipped where lower is better. Domain score is the unweighted mean of available indicator z-scores within the domain. Country score is a weighted mean across the nine domain scores. Sporadic series are linearly interpolated and held constant before the first and after the last observation.`;
  }
  const stamp = document.getElementById("data-stamp");
  if (stamp) stamp.textContent = `Data refreshed ${data.generated_at.slice(0, 10)}`;
}
