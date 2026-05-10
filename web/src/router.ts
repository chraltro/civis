/** Hash routing: #overview, #material, #health, ..., #wellbeing. */

import { setTab, state } from "./state";

const VALID_TABS = new Set<string>();

export function initRouter(domains: string[]): void {
  VALID_TABS.add("overview");
  for (const d of domains) VALID_TABS.add(slugify(d));

  const apply = () => {
    const slug = (window.location.hash || "#overview").slice(1).toLowerCase();
    const tab = resolveTab(slug, domains);
    setTab(tab);
  };
  window.addEventListener("hashchange", apply);
  apply();
}

export function navigate(tab: string): void {
  const slug = tab === "overview" ? "overview" : slugify(tab);
  if (window.location.hash !== `#${slug}`) {
    window.location.hash = `#${slug}`;
  } else {
    setTab(tab);
  }
}

export function slugify(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

function resolveTab(slug: string, domains: string[]): string {
  if (slug === "overview" || !VALID_TABS.has(slug)) return "overview";
  for (const d of domains) if (slugify(d) === slug) return d;
  return "overview";
}

export { state };
