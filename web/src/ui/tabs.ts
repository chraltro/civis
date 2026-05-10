/** Tab strip: Overview + each domain. */

import { navigate, slugify } from "../router";
import { state } from "../state";

export function buildTabs(host: HTMLElement, domains: string[]): void {
  host.innerHTML = "";
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
    a.addEventListener("click", (e) => {
      e.preventDefault();
      navigate(t.key);
    });
    host.appendChild(a);
  }
  syncTabsActive(host);
}

export function syncTabsActive(host: HTMLElement): void {
  for (const a of host.querySelectorAll<HTMLAnchorElement>(".tab")) {
    a.classList.toggle("active", a.dataset.key === state.tab);
  }
}
