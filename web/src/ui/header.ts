/** Country pickers + swap button + weights/about toggles. */

import type { CivisData } from "../data";
import { setHighlight, state, swap } from "../state";

export function buildHeader(data: CivisData): void {
  const sorted = data.countries
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name));
  const opts = sorted.map((c) => `<option value="${c.iso}">${c.name}</option>`).join("");

  const a = document.getElementById("sel-a") as HTMLSelectElement | null;
  const b = document.getElementById("sel-b") as HTMLSelectElement | null;
  if (!a || !b) return;
  a.innerHTML = opts;
  b.innerHTML = opts;
  a.value = state.hlA;
  b.value = state.hlB;

  a.addEventListener("change", () => {
    setHighlight("A", a.value);
    a.value = state.hlA;
    b.value = state.hlB;
  });
  b.addEventListener("change", () => {
    setHighlight("B", b.value);
    a.value = state.hlA;
    b.value = state.hlB;
  });
  document.getElementById("swap")?.addEventListener("click", () => {
    swap();
    a.value = state.hlA;
    b.value = state.hlB;
  });

  for (const id of ["weights-toggle", "about-toggle"] as const) {
    document.getElementById(id)?.addEventListener("click", () => {
      const panelId = id === "weights-toggle" ? "weights-panel" : "about-panel";
      const otherId = panelId === "weights-panel" ? "about-panel" : "weights-panel";
      document.getElementById(otherId)?.setAttribute("hidden", "");
      const panel = document.getElementById(panelId);
      if (panel) {
        if (panel.hasAttribute("hidden")) panel.removeAttribute("hidden");
        else panel.setAttribute("hidden", "");
      }
    });
  }
}

export function syncHeaderFromState(): void {
  const a = document.getElementById("sel-a") as HTMLSelectElement | null;
  const b = document.getElementById("sel-b") as HTMLSelectElement | null;
  if (a) a.value = state.hlA;
  if (b) b.value = state.hlB;
}
