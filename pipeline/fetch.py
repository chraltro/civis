"""Data fetchers for Civis sources.

Two backends:
  - World Bank WDI (REST API, returns JSON, ISO3 country filter)
  - Our World in Data (CSV via grapher slug)

Both write per-source CSVs into data/raw/, keyed by indicator key + source ref,
so subsequent runs can short-circuit if the upstream hasn't changed.

The OWID column-name resolution is part of the fetch step: each indicator
declares one or more candidate column names, and the fetcher picks whichever
is present, recording its choice in a small manifest so process.py can audit
later if a column rename happens.

Reliability:
  - Every HTTP GET goes through `_get_with_retry`, which retries with
    exponential backoff on transient failures (read/connect timeouts,
    protocol errors, 5xx responses, 429s).
  - `fetch_all` isolates failures per source. If one indicator's source is
    persistently broken, the rest still get fetched. The aggregate is reported
    in the final manifest, and the function raises at the end if any source
    failed, so CI marks the run as failed without losing the partial state.
"""

from __future__ import annotations

import io
import json
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pandas as pd

from .countries import ISO3_LIST, normalize_to_iso3
from .indicators import INDICATORS, Indicator, Source

log = logging.getLogger(__name__)

WB_BASE = "https://api.worldbank.org/v2"
OWID_BASE = "https://ourworldindata.org/grapher"
USER_AGENT = "civis-index/0.1 (+https://github.com/chraltro/civis)"

# A connect timeout of 15s and a read timeout of 60s. The retry layer tries
# again on transient failures.
DEFAULT_TIMEOUT = httpx.Timeout(connect=15.0, read=60.0, write=15.0, pool=15.0)
RETRY_BACKOFF_S: tuple[float, ...] = (2.0, 5.0, 12.0)
TRANSIENT_EXC = (
    httpx.ReadTimeout,
    httpx.ConnectTimeout,
    httpx.PoolTimeout,
    httpx.ReadError,
    httpx.RemoteProtocolError,
    httpx.ConnectError,
)


@dataclass
class FetchResult:
    indicator_key: str
    source_kind: str
    source_ref: str
    column_used: str | None
    n_rows: int
    n_countries: int
    csv_path: Path


@dataclass
class FetchFailure:
    indicator_key: str
    source_kind: str
    source_ref: str
    error: str


# --------------------------------------------------------------------------
# Retry layer
# --------------------------------------------------------------------------
def _get_with_retry(
    client: httpx.Client,
    url: str,
    params: dict | None = None,
    *,
    backoff: tuple[float, ...] = RETRY_BACKOFF_S,
) -> httpx.Response:
    """GET with exponential backoff on transient network/server failures.

    Retries on:
      - connection / read / pool timeouts
      - protocol errors (server hung up mid-response)
      - HTTP 5xx
      - HTTP 429 (rate limit)
    Raises immediately on:
      - HTTP 4xx other than 429 (likely a wrong URL; retrying won't help)
    """
    last_exc: Exception | None = None
    attempts = len(backoff) + 1
    for attempt in range(1, attempts + 1):
        try:
            r = client.get(url, params=params)
            if r.status_code in (429,) or 500 <= r.status_code < 600:
                # treat as transient
                msg = f"{r.status_code} {r.reason_phrase}"
                if attempt < attempts:
                    wait = backoff[attempt - 1]
                    log.warning("  HTTP %s on %s, retry %d/%d in %.1fs",
                                msg, url, attempt, attempts - 1, wait)
                    time.sleep(wait)
                    continue
                r.raise_for_status()  # will raise
            r.raise_for_status()
            return r
        except TRANSIENT_EXC as e:
            last_exc = e
            if attempt < attempts:
                wait = backoff[attempt - 1]
                log.warning("  %s on %s, retry %d/%d in %.1fs",
                            type(e).__name__, url, attempt, attempts - 1, wait)
                time.sleep(wait)
                continue
            raise
        except httpx.HTTPStatusError as e:
            # 4xx other than 429 — don't retry.
            raise e
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("unreachable")


# --------------------------------------------------------------------------
# World Bank WDI
# --------------------------------------------------------------------------
def fetch_wb_indicator(client: httpx.Client, code: str) -> pd.DataFrame:
    """Pull a WB indicator for all 29 countries, all years, into a long DF.

    Returns columns: iso3, year, value.
    """
    countries = ";".join(ISO3_LIST)
    url = f"{WB_BASE}/country/{countries}/indicator/{code}"
    params = {"format": "json", "per_page": 20000, "date": "1990:2025"}
    log.info("WB fetch %s", code)
    r = _get_with_retry(client, url, params=params)
    body = r.json()
    if not isinstance(body, list) or len(body) < 2:
        raise RuntimeError(f"unexpected WB response for {code}: {body!r}")
    rows = body[1] or []
    out = []
    for row in rows:
        iso3 = (row.get("countryiso3code") or "").upper()
        if iso3 not in ISO3_LIST:
            continue
        year = row.get("date")
        val = row.get("value")
        if val is None or year is None:
            continue
        out.append({"iso3": iso3, "year": int(year), "value": float(val)})
    df = pd.DataFrame(out, columns=["iso3", "year", "value"])
    return df.sort_values(["iso3", "year"]).reset_index(drop=True)


# --------------------------------------------------------------------------
# Our World in Data
# --------------------------------------------------------------------------
def fetch_owid_csv(client: httpx.Client, slug: str) -> pd.DataFrame:
    """Pull an OWID grapher CSV. Returns the raw DataFrame (no column choice)."""
    url = f"{OWID_BASE}/{slug}.csv"
    params = {"v": "1", "csvType": "full", "useColumnShortNames": "true"}
    log.info("OWID fetch %s", slug)
    r = _get_with_retry(client, url, params=params)
    return pd.read_csv(io.StringIO(r.text))


def resolve_owid_column(df: pd.DataFrame, candidates: tuple[str, ...] | str | None) -> str:
    """Find the value column in an OWID CSV.

    Strategy:
      1. If candidates is a string, return it (and assert presence).
      2. If candidates is a tuple, return the first one that exists.
      3. If candidates is None or nothing matches, infer: take the only
         numeric column that isn't 'Year' or 'Code'.
    """
    if isinstance(candidates, str):
        if candidates in df.columns:
            return candidates
        raise KeyError(f"expected column {candidates!r} not in OWID CSV; cols={list(df.columns)}")
    if isinstance(candidates, tuple):
        for c in candidates:
            if c in df.columns:
                return c
        # fall through to inference
    excluded = {"Year", "year", "Code", "code", "Entity", "entity"}
    numeric_cols = [
        c for c in df.columns
        if c not in excluded and pd.api.types.is_numeric_dtype(df[c])
    ]
    if len(numeric_cols) == 1:
        return numeric_cols[0]
    raise KeyError(
        f"could not resolve OWID value column. candidates={candidates!r}, "
        f"present={list(df.columns)}, numeric={numeric_cols}"
    )


def normalize_owid_long(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    """Convert raw OWID CSV (Entity, Code, Year, <value_col>) to (iso3, year, value)."""
    iso_col = "Code" if "Code" in df.columns else "code"
    yr_col = "Year" if "Year" in df.columns else "year"
    ent_col = "Entity" if "Entity" in df.columns else "entity"
    out = []
    for _, row in df.iterrows():
        code = row.get(iso_col)
        if pd.isna(code) or not code:
            code = normalize_to_iso3(str(row.get(ent_col, "")))
        if not code or code not in ISO3_LIST:
            continue
        year = row.get(yr_col)
        val = row.get(value_col)
        if pd.isna(year) or pd.isna(val):
            continue
        out.append({"iso3": str(code), "year": int(year), "value": float(val)})
    return (
        pd.DataFrame(out, columns=["iso3", "year", "value"])
        .sort_values(["iso3", "year"])
        .reset_index(drop=True)
    )


# --------------------------------------------------------------------------
# Per-source dispatcher
# --------------------------------------------------------------------------
def fetch_source(
    client: httpx.Client,
    indicator: Indicator,
    source: Source,
    raw_dir: Path,
) -> FetchResult:
    """Fetch one (indicator, source) pair, write CSV, return metadata."""
    if source.kind == "wb":
        df = fetch_wb_indicator(client, source.ref)
        column_used = None
    elif source.kind == "owid":
        raw = fetch_owid_csv(client, source.ref)
        column_used = resolve_owid_column(raw, source.column)
        df = normalize_owid_long(raw, column_used)
    else:
        raise ValueError(f"unknown source kind: {source.kind}")

    if source.scale != 1.0:
        df = df.copy()
        df["value"] = df["value"] * source.scale

    csv_path = raw_dir / f"{indicator.key}__{source.kind}__{source.ref.replace('/', '_')}.csv"
    df.to_csv(csv_path, index=False)
    return FetchResult(
        indicator_key=indicator.key,
        source_kind=source.kind,
        source_ref=source.ref,
        column_used=column_used,
        n_rows=len(df),
        n_countries=df["iso3"].nunique() if len(df) else 0,
        csv_path=csv_path,
    )


# --------------------------------------------------------------------------
# Top-level runner
# --------------------------------------------------------------------------
def fetch_all(raw_dir: Path, *, sleep_s: float = 0.2) -> list[FetchResult]:
    """Fetch every source for every indicator. Writes a manifest at the end.

    Per-source isolation: a single failure does not abort the run. The other
    indicators still get fetched, the manifest records both successes and
    failures, and the function raises a single RuntimeError at the end if
    any source ultimately failed (after retries). That way CI marks the run
    as failed without throwing away the partial fetch state.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    results: list[FetchResult] = []
    failures: list[FetchFailure] = []
    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(timeout=DEFAULT_TIMEOUT, headers=headers, follow_redirects=True) as client:
        for ind in INDICATORS:
            for src in ind.sources:
                try:
                    res = fetch_source(client, ind, src, raw_dir)
                    results.append(res)
                    log.info(
                        "  %s [%s:%s] -> %d rows, %d countries",
                        ind.key, src.kind, src.ref, res.n_rows, res.n_countries,
                    )
                except Exception as e:  # noqa: BLE001
                    log.error("  %s [%s:%s] FAILED after retries: %s",
                              ind.key, src.kind, src.ref, e)
                    failures.append(FetchFailure(
                        indicator_key=ind.key,
                        source_kind=src.kind,
                        source_ref=src.ref,
                        error=f"{type(e).__name__}: {e}",
                    ))
                time.sleep(sleep_s)

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "n_sources_ok": len(results),
        "n_sources_failed": len(failures),
        "sources": [
            {
                "indicator": r.indicator_key,
                "kind": r.source_kind,
                "ref": r.source_ref,
                "column_used": r.column_used,
                "n_rows": r.n_rows,
                "n_countries": r.n_countries,
                "csv": r.csv_path.name,
            }
            for r in results
        ],
        "failures": [
            {
                "indicator": f.indicator_key,
                "kind": f.source_kind,
                "ref": f.source_ref,
                "error": f.error,
            }
            for f in failures
        ],
    }
    (raw_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    if failures:
        # Raise at end so the manifest is written first.
        summary = ", ".join(f"{f.indicator_key}({f.source_kind})" for f in failures)
        raise RuntimeError(
            f"{len(failures)} source(s) failed after retries: {summary}. "
            f"See {raw_dir / 'manifest.json'} for details."
        )
    return results


__all__ = [
    "fetch_all",
    "fetch_source",
    "fetch_wb_indicator",
    "fetch_owid_csv",
    "resolve_owid_column",
    "normalize_owid_long",
    "FetchResult",
    "FetchFailure",
]
