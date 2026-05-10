/** Tab strip: Overview + each domain.
 *
 * Keyboard navigation: ArrowLeft/Right to step, Home/End to jump, Enter to
 * activate. Active tab is scrolled into view on mobile so it never falls off
 * the edge of the horizontal strip.
 */

import { navigate, slugify } from "../router";
import { state } from "../state";

export function buildTabs(host: HTMLElement, domains: string[]): void {
  host.innerHTML = "";
  host.setAttribute("role", "tablist");
  const tabs: { label: string; key: string }[] = [
    { label: "Overview", key: "overview" },
    ...domains.map((d) => ({ label: d, key: d })),
  ];
  for (const t of tabs) {
    const a = document.createElement("a");
    a.className = "tab";
    a.dataset.key = t.key;
    a.href = `#${t.key === "overview" ? "overview" : slugify(t.key)}`;
    a.textContent = t.label;
    a.setAttribute("role", "tab");
    a.addEventListener("click", (e) => {
      e.preventDefault();
      navigate(t.key);
    });
    host.appendChild(a);
  }

  host.addEventListener("keydown", (e) => {
    const navKeys = ["ArrowLeft", "ArrowRight", "Home", "End"];
    if (!navKeys.includes(e.key)) return;
    const all = Array.from(host.querySelectorAll<HTMLAnchorElement>(".tab"));
    const activeIdx = Math.max(0, all.findIndex((t) => t.classList.contains("active")));
    let nextIdx = activeIdx;
    if (e.key === "ArrowLeft") nextIdx = (activeIdx - 1 + all.length) % all.length;
    if (e.key === "ArrowRight") nextIdx = (activeIdx + 1) % all.length;
    if (e.key === "Home") nextIdx = 0;
    if (e.key === "End") nextIdx = all.length - 1;
    if (nextIdx !== activeIdx) {
      e.preventDefault();
      all[nextIdx].focus();
      all[nextIdx].click();
    }
  });

  syncTabsActive(host);
}

export function syncTabsActive(host: HTMLElement): void {
  for (const a of host.querySelectorAll<HTMLAnchorElement>(".tab")) {
    const active = a.dataset.key === state.tab;
    a.classList.toggle("active", active);
    a.setAttribute("aria-selected", active ? "true" : "false");
    a.tabIndex = active ? 0 : -1;
    if (active) {
      // Scroll active tab into view on mobile horizontal strip.
      a.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "smooth" });
    }
  }
}
