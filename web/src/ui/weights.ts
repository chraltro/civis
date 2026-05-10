import { resetWeights, setWeight, state } from "../state";

export function buildWeightSliders(domains: string[]): void {
  const grid = document.getElementById("weights-grid");
  if (!grid) return;
  grid.innerHTML = "";
  for (const d of domains) {
    const row = document.createElement("div");
    row.className = "weight-row";
    row.innerHTML = `
      <span class="name">${d}</span>
      <input type="range" min="0" max="3" step="0.1" value="${state.weights[d] ?? 1}" data-domain="${d}">
      <span class="val" data-val="${d}">${(state.weights[d] ?? 1).toFixed(1)}</span>
    `;
    grid.appendChild(row);
  }
  grid.querySelectorAll<HTMLInputElement>("input[type='range']").forEach((input) => {
    input.addEventListener("input", () => {
      const d = input.dataset.domain!;
      const val = parseFloat(input.value);
      setWeight(d, val);
      const valSpan = grid.querySelector<HTMLElement>(`[data-val="${d}"]`);
      if (valSpan) valSpan.textContent = val.toFixed(1);
    });
  });
  document.getElementById("weights-reset")?.addEventListener("click", () => {
    resetWeights(domains);
    grid.querySelectorAll<HTMLInputElement>("input[type='range']").forEach((input) => {
      input.value = "1.0";
      const valSpan = grid.querySelector<HTMLElement>(`[data-val="${input.dataset.domain}"]`);
      if (valSpan) valSpan.textContent = "1.0";
    });
  });
}
