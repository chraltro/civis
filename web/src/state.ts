/**
 * Civis client state.
 *
 * Three things change at runtime:
 *   - which tab is showing (overview | one of the 9 domains)
 *   - the two highlighted countries (A in sage, B in amber)
 *   - the per-domain weights (default 1.0 each, normalized at compute time)
 *
 * Subscribers receive a single callback when any of these change. No framework.
 */

import type { CivisData } from "./data";

export type Tab = "overview" | string; // 'overview' or a domain name

export type Listener = () => void;

export interface State {
  tab: Tab;
  hlA: string;
  hlB: string;
  weights: Record<string, number>;
}

const listeners = new Set<Listener>();

export const state: State = {
  tab: "overview",
  hlA: "NOR",
  hlB: "USA",
  weights: {},
};

export function initWeights(domains: string[]): void {
  for (const d of domains) state.weights[d] = 1.0;
}

export function setTab(tab: Tab): void {
  if (state.tab === tab) return;
  state.tab = tab;
  emit();
}

export function setHighlight(slot: "A" | "B", iso: string): void {
  if (slot === "A") {
    if (iso === state.hlB) state.hlB = state.hlA;
    state.hlA = iso;
  } else {
    if (iso === state.hlA) state.hlA = state.hlB;
    state.hlB = iso;
  }
  emit();
}

export function swap(): void {
  [state.hlA, state.hlB] = [state.hlB, state.hlA];
  emit();
}

export function setWeight(domain: string, value: number): void {
  state.weights[domain] = value;
  emit();
}

export function resetWeights(domains: string[]): void {
  for (const d of domains) state.weights[d] = 1.0;
  emit();
}

export function subscribe(fn: Listener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function emit(): void {
  for (const fn of listeners) fn();
}

// ----------------------------------------------------------------
// Composite computation from current weights.
// ----------------------------------------------------------------

export interface CompositeContext {
  composite: Record<string, (number | null)[]>;
  latest: Record<string, number>;
  ranked: string[];
}

export function computeComposite(data: CivisData): CompositeContext {
  const weights = normalizedWeights(data.domains);
  const composite: Record<string, (number | null)[]> = {};
  for (const c of data.countries) {
    const arr: (number | null)[] = [];
    for (let yi = 0; yi < data.years.length; yi++) {
      let sum = 0;
      let wsum = 0;
      for (const d of data.domains) {
        const v = data.domain_z[d]?.[c.iso]?.[yi];
        if (v != null) {
          sum += weights[d] * v;
          wsum += weights[d];
        }
      }
      arr.push(wsum > 0 ? sum / wsum : null);
    }
    composite[c.iso] = arr;
  }
  const latestIdx = data.years.indexOf(Math.max(...data.years));
  const latest: Record<string, number> = {};
  for (const c of data.countries) {
    const v = composite[c.iso][latestIdx];
    if (v != null) latest[c.iso] = v;
  }
  const ranked = data.countries
    .map((c) => c.iso)
    .filter((iso) => latest[iso] != null)
    .sort((a, b) => latest[b] - latest[a]);
  return { composite, latest, ranked };
}

function normalizedWeights(domains: string[]): Record<string, number> {
  const total = domains.reduce((s, d) => s + (state.weights[d] ?? 1), 0) || 1;
  const out: Record<string, number> = {};
  for (const d of domains) out[d] = (state.weights[d] ?? 1) / total;
  return out;
}

// ----------------------------------------------------------------
// Per-domain / per-indicator helpers — used by domain views.
// ----------------------------------------------------------------

/** Latest year value at index. */
export function latestZ(
  series: Record<string, (number | null)[]> | undefined,
  iso: string,
  yi: number,
): number | null {
  return series?.[iso]?.[yi] ?? null;
}

/** Rank an iso among all countries on a numeric value (descending = best first). */
export function rankBy(
  data: CivisData,
  valueOf: (iso: string) => number | null,
): Map<string, number> {
  const pairs = data.countries
    .map((c) => ({ iso: c.iso, v: valueOf(c.iso) }))
    .filter((p): p is { iso: string; v: number } => p.v != null)
    .sort((a, b) => b.v - a.v);
  const out = new Map<string, number>();
  pairs.forEach((p, i) => out.set(p.iso, i + 1));
  return out;
}
