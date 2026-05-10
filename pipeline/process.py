"""Civis Index processing.

Pipeline:
  1. Load per-source long DFs from data/raw/.
  2. Merge primary + fallback sources for each indicator (with scale-mismatch
     guards).
  3. Build an indicator panel: index = (iso3, year), columns = indicator keys.
  4. Linear-interpolate within each country's observed range; hold constant
     before first / after last observation.
  5. Compute panel-wide z-scores (across all 29 countries × all years).
  6. Winsorize at ±2.5σ.
  7. Sign-flip 'down' indicators.
  8. Aggregate: domain z = unweighted mean of indicator z within domain.
  9. Aggregate: composite z = unweighted mean of domain z (weights are applied
     CLIENT-SIDE in the dashboard, not here).
 10. Emit data/processed/civis.json + civis.csv.

Two important methodological decisions baked in:
  * Z-scoring is panel-wide, not per-year. A country at z=0 in 2023 means
    "average across the entire 1990–2023 sample," which makes time
    trajectories comparable to the long-run baseline.
  * Mean (not median) is used for aggregation, because winsorization at
    ±2.5σ already handles outliers. Median would throw away signal.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from .countries import COUNTRIES, ISO3_LIST
from .indicators import DOMAINS, INDICATORS, INDICATORS_BY_DOMAIN, Indicator

log = logging.getLogger(__name__)

YEAR_MIN = 1990
YEAR_MAX = 2023
YEARS = list(range(YEAR_MIN, YEAR_MAX + 1))
WINSOR_LIMIT = 2.5


@dataclass
class ProcessConfig:
    raw_dir: Path
    out_dir: Path
    snapshot_dir: Path | None = None


# --------------------------------------------------------------------------
# Source loading + merge
# --------------------------------------------------------------------------
def _load_source_csv(raw_dir: Path, indicator_key: str, kind: str, ref: str) -> pd.DataFrame:
    name = f"{indicator_key}__{kind}__{ref.replace('/', '_')}.csv"
    path = raw_dir / name
    if not path.exists():
        return pd.DataFrame(columns=["iso3", "year", "value"])
    df = pd.read_csv(path)
    df["iso3"] = df["iso3"].astype(str)
    df["year"] = df["year"].astype(int)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna(subset=["value"])


def _merge_sources(indicator: Indicator, raw_dir: Path) -> pd.DataFrame:
    """Combine primary + fallback sources for one indicator.

    First source wins where both are present. Subsequent sources fill gaps.
    Before merging, we run a sanity check: if two sources differ by more than
    5x in median scale, raise — they're not on the same scale.
    """
    frames: list[tuple[str, pd.DataFrame]] = []
    for src in indicator.sources:
        df = _load_source_csv(raw_dir, indicator.key, src.kind, src.ref)
        if not df.empty:
            frames.append((f"{src.kind}:{src.ref}", df))
    if not frames:
        return pd.DataFrame(columns=["iso3", "year", "value"])
    if len(frames) == 1:
        return frames[0][1]

    # Scale-mismatch guard
    medians = [(name, df["value"].median()) for name, df in frames]
    nonzero = [m for _, m in medians if m and abs(m) > 0]
    if len(nonzero) >= 2:
        ratio = max(abs(m) for m in nonzero) / max(min(abs(m) for m in nonzero), 1e-9)
        if ratio > 5.0:
            raise ValueError(
                f"scale mismatch on {indicator.key}: medians {medians}. "
                "Are these sources on the same scale? Add a Source.scale to "
                "rescale, or fix the manifest."
            )

    primary_name, primary = frames[0]
    log.info("  %s: primary %s", indicator.key, primary_name)
    out = primary.copy()
    have = set(zip(out["iso3"], out["year"], strict=True))
    for name, df in frames[1:]:
        keys = list(zip(df["iso3"], df["year"], strict=True))
        mask = [k not in have for k in keys]
        added = df[mask]
        if len(added):
            log.info("  %s: fallback %s adds %d rows", indicator.key, name, len(added))
            out = pd.concat([out, added], ignore_index=True)
            have |= set(zip(added["iso3"], added["year"], strict=True))
    return out.sort_values(["iso3", "year"]).reset_index(drop=True)


# --------------------------------------------------------------------------
# Interpolation
# --------------------------------------------------------------------------
def _interpolate_country(series: pd.Series, years: list[int]) -> pd.Series:
    """Linear within observed range, held constant before first / after last."""
    s = series.reindex(years).copy()
    if s.isna().all():
        return s
    first = s.first_valid_index()
    last = s.last_valid_index()
    inside = s.loc[first:last]
    inside = inside.interpolate(method="linear", limit_direction="both")
    s.loc[first:last] = inside
    s.loc[:first] = s.loc[first]
    s.loc[last:] = s.loc[last]
    return s


def build_indicator_panel(raw_dir: Path) -> pd.DataFrame:
    """Long DF with index (iso3, year), columns = indicator keys, interpolated.

    Missing countries / years are *kept as NaN* if the indicator has no
    observations for that country anywhere in the panel; this surfaces in
    coverage checks rather than being silently filled.
    """
    rows: dict[tuple[str, int], dict[str, float]] = {
        (iso, y): {} for iso in ISO3_LIST for y in YEARS
    }
    for ind in INDICATORS:
        merged = _merge_sources(ind, raw_dir)
        if merged.empty:
            log.warning("  %s: NO observations from any source", ind.key)
            continue
        merged = merged[merged["year"].between(YEAR_MIN, YEAR_MAX)]
        # If country has zero observations we leave it NaN; otherwise interpolate.
        for iso in ISO3_LIST:
            country_df = merged[merged["iso3"] == iso].set_index("year")["value"]
            if country_df.empty:
                continue
            interp = _interpolate_country(country_df, YEARS)
            for y, v in interp.items():
                if pd.notna(v):
                    rows[(iso, y)][ind.key] = float(v)
    panel = pd.DataFrame.from_dict(rows, orient="index")
    panel.index = pd.MultiIndex.from_tuples(panel.index, names=["iso3", "year"])
    panel = panel.reindex(columns=[i.key for i in INDICATORS])
    return panel.sort_index()


# --------------------------------------------------------------------------
# Z-scoring + aggregation
# --------------------------------------------------------------------------
def _zscore_panel(values: pd.Series) -> pd.Series:
    """Panel-wide z-score across all (country, year) observations."""
    mu = values.mean(skipna=True)
    sigma = values.std(ddof=0, skipna=True)
    if sigma == 0 or pd.isna(sigma):
        return values * 0.0
    return (values - mu) / sigma


def compute_indicator_z(panel: pd.DataFrame) -> pd.DataFrame:
    """Z-score each indicator panel-wide, winsorize at ±2.5σ, sign-flip down."""
    z = pd.DataFrame(index=panel.index, columns=panel.columns, dtype=float)
    for ind in INDICATORS:
        col = panel[ind.key]
        zcol = _zscore_panel(col)
        zcol = zcol.clip(lower=-WINSOR_LIMIT, upper=WINSOR_LIMIT)
        if ind.direction == "down":
            zcol = -zcol
        z[ind.key] = zcol
    return z


def compute_domain_z(z_indicators: pd.DataFrame) -> pd.DataFrame:
    """Domain z = unweighted mean of available indicator z within the domain."""
    cols = list(DOMAINS)
    out = pd.DataFrame(index=z_indicators.index, columns=cols, dtype=float)
    for d in DOMAINS:
        keys = [i.key for i in INDICATORS_BY_DOMAIN[d]]
        present = [k for k in keys if k in z_indicators.columns]
        out[d] = z_indicators[present].mean(axis=1, skipna=True)
    return out


def compute_composite(z_domains: pd.DataFrame) -> pd.DataFrame:
    """Composite = unweighted mean of domain z. (Weights are user-side.)"""
    return z_domains.mean(axis=1, skipna=True).to_frame("composite")


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------
def _ranked_by_latest(latest: dict[str, float]) -> list[str]:
    return sorted(
        ISO3_LIST,
        key=lambda iso: (latest.get(iso) if latest.get(iso) is not None else -1e9),
        reverse=True,
    )


def _series_for(panel: pd.DataFrame, col: str, iso: str) -> list[float | None]:
    if col not in panel.columns:
        return [None] * len(YEARS)
    sub = panel.xs(iso, level="iso3")[col]
    return [None if pd.isna(v) else float(v) for v in sub.reindex(YEARS).values]


def to_dashboard_json(
    panel: pd.DataFrame,
    z_indicators: pd.DataFrame,
    z_domains: pd.DataFrame,
    composite: pd.DataFrame,
) -> dict:
    """Shape required by the dashboard.

    schema_version = 2 carries both z-scores and raw values plus per-indicator
    display formatting (precision/prefix/suffix), so the web can render
    "97% internet users" alongside "z=+1.24" without a second fetch.
    """
    countries = [{"iso": c.iso3, "name": c.name} for c in COUNTRIES]
    indicators_meta = [
        {
            "key": i.key,
            "label": i.label,
            "domain": i.domain,
            "direction": i.direction,
            "precision": i.precision,
            "prefix": i.prefix,
            "suffix": i.suffix,
        }
        for i in INDICATORS
    ]
    z = {
        i.key: {iso: _series_for(z_indicators, i.key, iso) for iso in ISO3_LIST}
        for i in INDICATORS
    }
    raw = {
        i.key: {iso: _series_for(panel, i.key, iso) for iso in ISO3_LIST}
        for i in INDICATORS
    }
    domain_z = {
        d: {iso: _series_for(z_domains, d, iso) for iso in ISO3_LIST}
        for d in DOMAINS
    }
    composite_series = {
        iso: _series_for(composite, "composite", iso) for iso in ISO3_LIST
    }
    latest_idx = YEARS.index(YEAR_MAX)
    latest = {
        iso: composite_series[iso][latest_idx] for iso in ISO3_LIST
        if composite_series[iso][latest_idx] is not None
    }
    return {
        "schema_version": 2,
        "generated_at": datetime.now(UTC).isoformat(),
        "years": YEARS,
        "countries": countries,
        "domains": list(DOMAINS),
        "indicators": indicators_meta,
        "z": z,
        "raw": raw,
        "domain_z": domain_z,
        "composite": composite_series,
        "latest": latest,
        "ranked": _ranked_by_latest(latest),
    }


def to_csv(panel: pd.DataFrame, z_indicators: pd.DataFrame) -> pd.DataFrame:
    """Flat indicator × country × year CSV: raw values + z-scores side by side."""
    rows = []
    for (iso, year), row in panel.iterrows():
        z_row = z_indicators.loc[(iso, year)] if (iso, year) in z_indicators.index else None
        for ind in INDICATORS:
            v = row.get(ind.key)
            zv = z_row.get(ind.key) if z_row is not None else None
            rows.append({
                "iso3": iso,
                "year": year,
                "indicator": ind.key,
                "domain": ind.domain,
                "direction": ind.direction,
                "value": None if pd.isna(v) else float(v),
                "z": None if zv is None or pd.isna(zv) else float(zv),
            })
    return pd.DataFrame(rows)


def run(cfg: ProcessConfig) -> dict:
    """Top-level entry. Reads raw/, writes processed/, optionally snapshots."""
    cfg.out_dir.mkdir(parents=True, exist_ok=True)

    log.info("Building indicator panel from %s", cfg.raw_dir)
    panel = build_indicator_panel(cfg.raw_dir)
    log.info("  panel shape: %s", panel.shape)

    log.info("Z-scoring indicators (winsor=%.1f)", WINSOR_LIMIT)
    z_indicators = compute_indicator_z(panel)
    log.info("Aggregating to domain scores")
    z_domains = compute_domain_z(z_indicators)
    log.info("Aggregating to composite")
    composite = compute_composite(z_domains)

    out = to_dashboard_json(panel, z_indicators, z_domains, composite)
    out_json = cfg.out_dir / "civis.json"
    out_json.write_text(json.dumps(out, indent=None, separators=(",", ":")))
    log.info("Wrote %s (%d KB)", out_json, out_json.stat().st_size // 1024)

    csv_path = cfg.out_dir / "civis.csv"
    flat = to_csv(panel, z_indicators)
    flat.to_csv(csv_path, index=False)
    log.info("Wrote %s (%d rows)", csv_path, len(flat))

    if cfg.snapshot_dir is not None:
        cfg.snapshot_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y-%m-%d")
        snap = cfg.snapshot_dir / f"{stamp}-civis.json"
        snap.write_text(out_json.read_text())
        log.info("Wrote snapshot %s", snap)

    return out


__all__ = [
    "ProcessConfig",
    "run",
    "build_indicator_panel",
    "compute_indicator_z",
    "compute_domain_z",
    "compute_composite",
    "to_dashboard_json",
    "to_csv",
    "YEARS",
    "WINSOR_LIMIT",
]
