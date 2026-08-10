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

# The World Bank API sheds load by answering 400 Bad Request rather than 429 or
# 503. The same URL then returns 200 a few seconds later, so a 400 from WB says
# nothing about whether the request was well-formed. Retry it. A genuinely bad
# indicator code still fails, just after the backoff ladder instead of at once.
WB_RETRY_STATUSES = frozenset({400, 429})
# WB throttles harder than OWID, so give it a longer ladder.
WB_RETRY_BACKOFF_S: tuple[float, ...] = (3.0, 8.0, 20.0, 45.0)

# Gap between source requests. This is a weekly cron over ~30 indicators, so
# pacing costs under a minute and keeps us well clear of the throttle.
DEFAULT_SLEEP_S = 1.5
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
    retry_statuses: frozenset[int] = frozenset({429}),
) -> httpx.Response:
    """GET with exponential backoff on transient network/server failures.

    Retries on:
      - connection / read / pool timeouts
      - protocol errors (server hung up mid-response)
      - HTTP 5xx
      - any status in `retry_statuses` (429 by default)
    Raises immediately on:
      - any other 4xx (a wrong URL or a dead slug; retrying won't help)

    `retry_statuses` exists because the World Bank API answers 400 Bad Request
    when it is throttling, for requests that succeed on a later attempt. See
    WB_RETRY_STATUSES.
    """
    last_exc: Exception | None = None
    attempts = len(backoff) + 1
    for attempt in range(1, attempts + 1):
        try:
            r = client.get(url, params=params)
            if r.status_code in retry_statuses or 500 <= r.status_code < 600:
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
            # Non-retryable 4xx.
            raise e
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("unreachable")


# --------------------------------------------------------------------------
# World Bank WDI
# --------------------------------------------------------------------------
def fetch_wb_indicator(
    client: httpx.Client, code: str, db: int | None = None
) -> pd.DataFrame:
    """Pull a WB indicator for all 29 countries, all years, into a long DF.

    `db` selects a non-default World Bank source database (e.g. 3 for the
    Worldwide Governance Indicators). Omit it for plain WDI indicators.

    Returns columns: iso3, year, value.
    """
    countries = ";".join(ISO3_LIST)
    url = f"{WB_BASE}/country/{countries}/indicator/{code}"
    params: dict = {"format": "json", "per_page": 20000, "date": "1990:2025"}
    if db is not None:
        params["source"] = db
    log.info("WB fetch %s%s", code, f" (source={db})" if db is not None else "")
    r = _get_with_retry(
        client, url, params=params,
        backoff=WB_RETRY_BACKOFF_S, retry_statuses=WB_RETRY_STATUSES,
    )
    body = r.json()
    if not isinstance(body, list) or len(body) < 2:
        # WB signals a retired/renamed indicator with HTTP 200 and a one-element
        # body carrying a message, so surface that text instead of a bare repr.
        msg = ""
        if isinstance(body, list) and body and isinstance(body[0], dict):
            for m in body[0].get("message") or []:
                msg = f"{m.get('key')}: {m.get('value')}"
                break
        raise RuntimeError(
            f"WB returned no data series for {code}"
            f"{f' (source={db})' if db is not None else ''}"
            f"{f' - {msg}' if msg else f': {body!r}'}"
        )
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
        df = fetch_wb_indicator(client, source.ref, db=source.db)
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
def fetch_all(raw_dir: Path, *, sleep_s: float = DEFAULT_SLEEP_S) -> list[FetchResult]:
    """Fetch every source for every indicator. Writes a manifest at the end.

    Per-indicator success: an indicator counts as fetched if AT LEAST ONE of
    its sources succeeds. Per-source isolation: a single failed source does
    not abort the run, and we keep trying the next source for the same
    indicator. Only when ALL sources for an indicator fail do we record it
    as a fatal failure.

    The function raises a single RuntimeError at the end if any indicator
    has no working source. CI marks the run as failed without throwing
    away the partial fetch state (manifest is written first).
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    results: list[FetchResult] = []
    failures: list[FetchFailure] = []
    soft_failures: list[FetchFailure] = []  # source-level failures hidden by a sibling success
    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(timeout=DEFAULT_TIMEOUT, headers=headers, follow_redirects=True) as client:
        for ind in INDICATORS:
            ind_attempts: list[tuple[Source, FetchResult | Exception]] = []
            ind_succeeded = False
            for src in ind.sources:
                try:
                    res = fetch_source(client, ind, src, raw_dir)
                    ind_attempts.append((src, res))
                    results.append(res)
                    ind_succeeded = True
                    log.info(
                        "  %s [%s:%s] -> %d rows, %d countries",
                        ind.key, src.kind, src.ref, res.n_rows, res.n_countries,
                    )
                except Exception as e:  # noqa: BLE001
                    ind_attempts.append((src, e))
                    log.warning(
                        "  %s [%s:%s] failed (%s); %s",
                        ind.key, src.kind, src.ref, type(e).__name__,
                        "trying next source" if src is not ind.sources[-1] else "no more sources",
                    )
                # Pace every request, including successful ones. This used to sit
                # after the success `break`, so a healthy run hit the World Bank
                # API back to back and got throttled into 400s.
                time.sleep(sleep_s)
                if ind_succeeded:
                    break  # first success wins; stop trying alternates

            if not ind_succeeded:
                # Promote every per-source failure to a hard failure for this indicator.
                for src, payload in ind_attempts:
                    if isinstance(payload, Exception):
                        failures.append(FetchFailure(
                            indicator_key=ind.key,
                            source_kind=src.kind,
                            source_ref=src.ref,
                            error=f"{type(payload).__name__}: {payload}",
                        ))
                log.error("  %s: ALL %d source(s) failed", ind.key, len(ind_attempts))
            else:
                # Sibling failures (alternates that failed before the first success) are
                # informational only and recorded separately.
                for src, payload in ind_attempts:
                    if isinstance(payload, Exception):
                        soft_failures.append(FetchFailure(
                            indicator_key=ind.key,
                            source_kind=src.kind,
                            source_ref=src.ref,
                            error=f"{type(payload).__name__}: {payload}",
                        ))

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "n_indicators_total": len(INDICATORS),
        "n_indicators_ok": len(INDICATORS) - len({f.indicator_key for f in failures}),
        "n_indicators_failed": len({f.indicator_key for f in failures}),
        "n_sources_ok": len(results),
        "n_sources_failed": len(failures),
        "n_sources_soft_failed": len(soft_failures),
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
        "soft_failures": [
            {
                "indicator": f.indicator_key,
                "kind": f.source_kind,
                "ref": f.source_ref,
                "error": f.error,
            }
            for f in soft_failures
        ],
    }
    (raw_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    if failures:
        # Raise at end so the manifest is written first.
        summary = ", ".join(sorted({f.indicator_key for f in failures}))
        raise RuntimeError(
            f"{manifest['n_indicators_failed']} indicator(s) failed (no working source): "
            f"{summary}. See {raw_dir / 'manifest.json'} for details."
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
