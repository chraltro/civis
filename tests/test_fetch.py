"""Tests for pipeline.fetch retry layer + per-source isolation.

Network calls are mocked via httpx.MockTransport so the tests run offline.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pandas as pd
import pytest

from pipeline.fetch import (
    FetchFailure,
    _get_with_retry,
    fetch_all,
)


def _client_from_handler(handler) -> httpx.Client:
    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport)


# --------------------------------------------------------------------------
# Retry layer
# --------------------------------------------------------------------------
def test_retry_succeeds_after_two_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two ReadTimeouts then a 200; retry should swallow them and return."""
    monkeypatch.setattr("pipeline.fetch.RETRY_BACKOFF_S", (0.0, 0.0, 0.0))
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ReadTimeout("boom", request=request)
        return httpx.Response(200, json={"ok": True})

    with _client_from_handler(handler) as client:
        r = _get_with_retry(client, "https://example.test/x")
    assert r.status_code == 200
    assert calls["n"] == 3


def test_retry_gives_up_and_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """All attempts time out; the last exception propagates."""
    monkeypatch.setattr("pipeline.fetch.RETRY_BACKOFF_S", (0.0, 0.0))

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("nope", request=request)

    with _client_from_handler(handler) as client, pytest.raises(httpx.ReadTimeout):
        _get_with_retry(client, "https://example.test/x")


def test_retry_on_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    """503 then 200 — 5xx is treated as transient."""
    monkeypatch.setattr("pipeline.fetch.RETRY_BACKOFF_S", (0.0, 0.0))
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503) if calls["n"] == 1 else httpx.Response(200, json={"ok": True})

    with _client_from_handler(handler) as client:
        r = _get_with_retry(client, "https://example.test/x")
    assert r.status_code == 200
    assert calls["n"] == 2


def test_retry_does_not_retry_on_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """404 is permanent; retry must NOT swallow it."""
    monkeypatch.setattr("pipeline.fetch.RETRY_BACKOFF_S", (0.0, 0.0))
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(404)

    with _client_from_handler(handler) as client, pytest.raises(httpx.HTTPStatusError):
        _get_with_retry(client, "https://example.test/x")
    assert calls["n"] == 1


# --------------------------------------------------------------------------
# Per-source isolation in fetch_all
# --------------------------------------------------------------------------
def test_fetch_all_isolates_per_source_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A single source failing should not abort the others.

    Strategy: monkeypatch fetch_source to fail for one indicator key only;
    succeed for all others by writing a valid CSV. Assert that fetch_all
    raises (because there was a failure) but the manifest records both
    successful sources and the one failure.
    """
    from pipeline import fetch as fetch_module
    from pipeline.fetch import FetchResult
    from pipeline.indicators import INDICATORS

    monkeypatch.setattr(fetch_module, "RETRY_BACKOFF_S", (0.0,))
    target = INDICATORS[5].key  # arbitrary indicator to fail

    def fake_fetch_source(client, indicator, source, raw_dir: Path):  # noqa: ANN001
        if indicator.key == target:
            raise httpx.ReadTimeout("simulated", request=httpx.Request("GET", "x"))
        # Write a one-row CSV so the manifest accountancy works.
        csv = raw_dir / f"{indicator.key}__{source.kind}__{source.ref.replace('/', '_')}.csv"
        pd.DataFrame([{"iso3": "USA", "year": 2020, "value": 1.0}]).to_csv(csv, index=False)
        return FetchResult(
            indicator_key=indicator.key,
            source_kind=source.kind,
            source_ref=source.ref,
            column_used=None,
            n_rows=1,
            n_countries=1,
            csv_path=csv,
        )

    monkeypatch.setattr(fetch_module, "fetch_source", fake_fetch_source)

    with pytest.raises(RuntimeError, match=target):
        fetch_all(tmp_path, sleep_s=0.0)

    # manifest should still exist with the failure recorded
    import json
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["n_sources_failed"] >= 1
    failed_keys = {f["indicator"] for f in manifest["failures"]}
    assert target in failed_keys
    # plus most other indicators succeeded
    assert manifest["n_sources_ok"] >= 10


def test_fetch_failure_dataclass() -> None:
    """Sanity: the dataclass is a stable record we can serialize."""
    f = FetchFailure(indicator_key="x", source_kind="wb", source_ref="REF", error="oops")
    assert f.indicator_key == "x"
    assert f.error == "oops"
