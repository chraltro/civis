/**
 * Civis data loader & types.
 *
 * The dashboard reads a single JSON file produced by `civis process`.
 * Schema must stay in sync with pipeline/process.py::to_dashboard_json.
 */

export interface CountryMeta {
  iso: string;
  name: string;
}

export interface IndicatorMeta {
  key: string;
  label: string;
  domain: string;
  direction: "up" | "down";
  /** Display formatting (schema v2+). Optional for back-compat with v1 JSON. */
  precision?: number;
  prefix?: string;
  suffix?: string;
}

export interface CivisData {
  schema_version: number;
  generated_at: string;
  years: number[];
  countries: CountryMeta[];
  domains: string[];
  indicators: IndicatorMeta[];
  /** indicator z-scores, [indicatorKey][iso][yearIdx] */
  z: Record<string, Record<string, (number | null)[]>>;
  /** raw (interpolated) indicator values, [indicatorKey][iso][yearIdx] (schema v2+) */
  raw?: Record<string, Record<string, (number | null)[]>>;
  /** domain z-mean, [domain][iso][yearIdx] */
  domain_z: Record<string, Record<string, (number | null)[]>>;
  /** composite (unweighted), [iso][yearIdx] */
  composite: Record<string, (number | null)[]>;
  /** latest-year composite per country */
  latest: Record<string, number>;
  /** latest-year ISO ranking, best to worst */
  ranked: string[];
}

/** Format a raw indicator value with its prefix/precision/suffix. */
export function formatRaw(meta: IndicatorMeta, v: number | null): string {
  if (v == null) return "—";
  const precision = meta.precision ?? 1;
  const prefix = meta.prefix ?? "";
  const suffix = meta.suffix ?? "";
  // Use locale formatting for thousands separator on integer parts.
  const formatted = v.toLocaleString("en-US", {
    minimumFractionDigits: precision,
    maximumFractionDigits: precision,
  });
  return `${prefix}${formatted}${suffix}`;
}

// Vite serves /public at root; we symlink web/public/data -> data/processed.
// At deploy time the JSON ends up at <site>/data/civis.json.
const DATA_URL = "./data/civis.json";

export async function loadData(): Promise<CivisData | null> {
  try {
    const r = await fetch(DATA_URL);
    if (!r.ok) return null;
    const text = await r.text();
    if (!text.trim()) return null;
    return JSON.parse(text) as CivisData;
  } catch {
    return null;
  }
}

/** Build a lookup from ISO to display name. */
export function nameMap(data: CivisData): Record<string, string> {
  const m: Record<string, string> = {};
  for (const c of data.countries) m[c.iso] = c.name;
  return m;
}

/** Index of a year in the years array, or -1. */
export function yearIndex(data: CivisData, year: number): number {
  return data.years.indexOf(year);
}
