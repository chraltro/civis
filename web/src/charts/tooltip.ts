/**
 * Singleton floating tooltip used by all charts.
 *
 * Positioned in viewport coordinates (`position: fixed`), hidden by default.
 * Charts call showTooltip(html, x, y) on hover/touch and hideTooltip() on
 * leave. The tooltip is non-interactive (pointer-events: none) so it never
 * blocks the underlying hit area.
 */

let el: HTMLDivElement | null = null;

function ensureEl(): HTMLDivElement {
  if (el) return el;
  el = document.createElement("div");
  el.className = "tooltip";
  el.setAttribute("role", "tooltip");
  document.body.appendChild(el);
  return el;
}

export function showTooltip(html: string, clientX: number, clientY: number): void {
  const t = ensureEl();
  t.innerHTML = html;
  // Center horizontally on the cursor, position above with a small offset.
  // Clamp inside the viewport so the tooltip never falls off-screen.
  t.style.left = "0px";
  t.style.top = "0px";
  t.style.transform = "translate(0, 0)"; // reset to measure
  t.style.opacity = "1";
  const rect = t.getBoundingClientRect();
  const margin = 6;
  let x = clientX - rect.width / 2;
  let y = clientY - rect.height - 10;
  if (x < margin) x = margin;
  if (x + rect.width > window.innerWidth - margin) x = window.innerWidth - rect.width - margin;
  if (y < margin) y = clientY + 16; // flip below cursor near top of viewport
  t.style.left = `${x}px`;
  t.style.top = `${y}px`;
}

export function hideTooltip(): void {
  if (!el) return;
  el.style.opacity = "0";
}
