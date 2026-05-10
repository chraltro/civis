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
# Per-indicator success in fetch_all
# --------------------------------------------------------------------------
def _fake_source_success(raw_dir: Path, indicator, source):  # noqa: ANN001
    """Helper: write a one-row CSV and return the corresponding FetchResult."""
    from pipeline.fetch import FetchResult

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


def test_fetch_all_indicator_with_no_working_source_is_a_hard_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An indicator whose every source fails should appear in `failures`."""
    from pipeline import fetch as fetch_module
    from pipeline.indicators import INDICATORS

    monkeypatch.setattr(fetch_module, "RETRY_BACKOFF_S", (0.0,))
    target = INDICATORS[5].key

    def fake_fetch_source(client, indicator, source, raw_dir: Path):  # noqa: ANN001
        if indicator.key == target:
            raise httpx.ReadTimeout("simulated", request=httpx.Request("GET", "x"))
        return _fake_source_success(raw_dir, indicator, source)

    monkeypatch.setattr(fetch_module, "fetch_source", fake_fetch_source)
    with pytest.raises(RuntimeError, match=target):
        fetch_all(tmp_path, sleep_s=0.0)

    import json
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    failed_keys = {f["indicator"] for f in manifest["failures"]}
    assert target in failed_keys
    assert manifest["n_indicators_failed"] >= 1
    assert manifest["n_sources_ok"] >= 10


def test_fetch_wb_indicator_passes_source_param() -> None:
    """WGI indicators need source=23 on the WB API. Verify the param threads through."""
    from pipeline.fetch import fetch_wb_indicator

    seen_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        # Standard WB envelope: [meta, rows]
        return httpx.Response(200, json=[{"page": 1, "pages": 1}, []])

    with _client_from_handler(handler) as client:
        # Default: no source param
        fetch_wb_indicator(client, "NY.GDP.PCAP.PP.KD")
        # WGI: source=23
        fetch_wb_indicator(client, "PV.EST", source=23)

    assert "source=" not in seen_urls[0]
    assert "source=23" in seen_urls[1]


def test_fetch_all_first_source_fails_but_fallback_succeeds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """If primary source 404s but a fallback succeeds, the run should NOT fail.

    Uses the press_freedom indicator (which now has multiple OWID slug
    candidates as fallbacks) as the target. Force the first slug to fail and
    the second to succeed, and assert: no hard failure, the soft failure is
    recorded, and the indicator counts as ok.
    """
    from pipeline import fetch as fetch_module
    from pipeline.indicators import INDICATORS_BY_KEY

    monkeypatch.setattr(fetch_module, "RETRY_BACKOFF_S", (0.0,))
    pf = INDICATORS_BY_KEY["press_freedom"]
    assert len(pf.sources) >= 2, "press_freedom must declare multiple slug candidates"
    fail_ref = pf.sources[0].ref

    calls: list[tuple[str, str]] = []

    def fake_fetch_source(client, indicator, source, raw_dir: Path):  # noqa: ANN001
        calls.append((indicator.key, source.ref))
        if indicator.key == "press_freedom" and source.ref == fail_ref:
            raise httpx.HTTPStatusError(
                "404 Not Found",
                request=httpx.Request("GET", "x"),
                response=httpx.Response(404, request=httpx.Request("GET", "x")),
            )
        return _fake_source_success(raw_dir, indicator, source)

    monkeypatch.setattr(fetch_module, "fetch_source", fake_fetch_source)
    # Should NOT raise — the fallback recovers.
    fetch_all(tmp_path, sleep_s=0.0)

    import json
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["n_indicators_failed"] == 0
    # The first slug should appear in soft_failures, not failures.
    soft_refs = {f["ref"] for f in manifest["soft_failures"]}
    assert fail_ref in soft_refs
    # And the run should have stopped trying alternates after the second succeeded.
    pf_calls = [(k, r) for k, r in calls if k == "press_freedom"]
    assert len(pf_calls) == 2
    assert pf_calls[0][1] == fail_ref
    assert pf_calls[1][1] == pf.sources[1].ref


def test_fetch_all_first_source_succeeds_does_not_try_alternates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When the primary source works, alternates should NOT be fetched."""
    from pipeline import fetch as fetch_module
    from pipeline.indicators import INDICATORS_BY_KEY

    monkeypatch.setattr(fetch_module, "RETRY_BACKOFF_S", (0.0,))
    pf = INDICATORS_BY_KEY["press_freedom"]
    calls: list[tuple[str, str]] = []

    def fake_fetch_source(client, indicator, source, raw_dir: Path):  # noqa: ANN001
        calls.append((indicator.key, source.ref))
        return _fake_source_success(raw_dir, indicator, source)

    monkeypatch.setattr(fetch_module, "fetch_source", fake_fetch_source)
    fetch_all(tmp_path, sleep_s=0.0)
    pf_calls = [(k, r) for k, r in calls if k == "press_freedom"]
    assert len(pf_calls) == 1, f"expected only primary, got {pf_calls}"
    assert pf_calls[0][1] == pf.sources[0].ref


def test_fetch_failure_dataclass() -> None:
    """Sanity: the dataclass is a stable record we can serialize."""
    f = FetchFailure(indicator_key="x", source_kind="wb", source_ref="REF", error="oops")
    assert f.indicator_key == "x"
    assert f.error == "oops"
