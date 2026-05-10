/**
 * Country highlight pickers + swap button.
 */

import type { CivisData } from "../data";
import { setHighlight, state, swap } from "../state";

export function buildControls(data: CivisData): void {
  const opts = data.countries
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((c) => `<option value="${c.iso}">${c.name}</option>`)
    .join("");
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
}

export function updateControlsFromState(): void {
  const a = document.getElementById("sel-a") as HTMLSelectElement | null;
  const b = document.getElementById("sel-b") as HTMLSelectElement | null;
  if (a) a.value = state.hlA;
  if (b) b.value = state.hlB;
  const nameOf = (window as unknown as { __civisNames?: Record<string, string> }).__civisNames ?? {};
  const legA = document.getElementById("legend-a");
  const legB = document.getElementById("legend-b");
  if (legA) legA.innerHTML = `<span style="color:#94b09e">sage = ${nameOf[state.hlA] ?? state.hlA}</span>`;
  if (legB) legB.innerHTML = `<span style="color:#d2965a">orange = ${nameOf[state.hlB] ?? state.hlB}</span>`;
}
