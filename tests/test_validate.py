"""Tests for pipeline.validate."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pipeline.process import (
    build_indicator_panel,
    compute_composite,
    compute_domain_z,
    compute_indicator_z,
)
from pipeline.validate import (
    check_directions,
    check_invariants,
    check_ranking_snapshot,
    check_scale_mismatch,
)


def test_directions_pass_on_synth_panel(populate_raw: Path) -> None:
    panel = build_indicator_panel(populate_raw)
    issues = check_directions(panel)
    assert not issues, f"unexpected direction failures: {[str(i) for i in issues]}"


def test_directions_catch_sign_flip(populate_raw: Path) -> None:
    """If we deliberately flip the sign of an indicator, the test catches it."""
    panel = build_indicator_panel(populate_raw)
    # Flip press_freedom: now high raw values come first instead of low.
    panel = panel.copy()
    panel["press_freedom"] = -panel["press_freedom"]
    issues = check_directions(panel)
    keys = {i.indicator for i in issues}
    assert "press_freedom" in keys, "direction check missed an obvious sign flip"


def test_invariants_pass_on_real_aggregation(populate_raw: Path) -> None:
    panel = build_indicator_panel(populate_raw)
    z = compute_indicator_z(panel)
    z_dom = compute_domain_z(z)
    comp = compute_composite(z_dom)
    issues = check_invariants(z, z_dom, comp)
    assert not issues


def test_invariants_catch_drift(populate_raw: Path) -> None:
    panel = build_indicator_panel(populate_raw)
    z = compute_indicator_z(panel)
    z_dom = compute_domain_z(z)
    # Corrupt one domain
    z_dom = z_dom.copy()
    z_dom.iloc[0, 0] = z_dom.iloc[0, 0] + 99
    comp = compute_composite(z_dom)
    issues = check_invariants(z, z_dom, comp)
    # Composite still recomputes from z_dom, so that's fine; but the domain
    # value won't match the mean of indicator z. So invariants should flag.
    assert any("domain" in i.message for i in issues)


def test_scale_mismatch_detector(tmp_path: Path) -> None:
    """Two sources differing by 100x in median should be flagged."""
    raw = tmp_path / "raw"
    raw.mkdir()
    # Pick an indicator with a single source; we manufacture a fake second source
    # using a separate filename. (The test uses indicator "gini" which we declare
    # to have potential dual sources via a fake additional file on disk.)
    # For a real scale-mismatch test we need two files with the same indicator key.
    # Easiest: use schooling (single source) and synthesize both files.
    from pipeline.indicators import Indicator, Source

    fake = Indicator(
        key="testdup",
        label="t",
        domain="Material",
        direction="up",
        sources=(
            Source("wb", "AAA"),
            Source("owid", "bbb"),
        ),
    )
    df1 = pd.DataFrame({"iso3": ["USA"], "year": [2020], "value": [100.0]})
    df2 = pd.DataFrame({"iso3": ["USA"], "year": [2020], "value": [1.0]})  # 100x off
    df1.to_csv(raw / f"{fake.key}__wb__AAA.csv", index=False)
    df2.to_csv(raw / f"{fake.key}__owid__bbb.csv", index=False)
    # We monkey-patch INDICATORS so the validator sees our fake indicator.
    import pipeline.indicators as mod
    original = mod.INDICATORS
    try:
        mod.INDICATORS = (*original, fake)
        issues = check_scale_mismatch(raw)
        scaled = [i for i in issues if i.indicator == "testdup"]
        assert scaled, "scale-mismatch detector missed a 100x disparity"
    finally:
        mod.INDICATORS = original


def test_ranking_snapshot_create_and_match(populate_raw: Path, tmp_path: Path) -> None:
    panel = build_indicator_panel(populate_raw)
    z = compute_indicator_z(panel)
    z_dom = compute_domain_z(z)
    comp = compute_composite(z_dom)
    snap = tmp_path / "ranking.json"
    # First call with --update: creates snapshot, no issues.
    issues = check_ranking_snapshot(comp, snap, update=True)
    assert not issues
    # Second call without update: should match, no issues.
    issues = check_ranking_snapshot(comp, snap, update=False)
    assert not issues


def test_ranking_snapshot_creates_parent_dir(populate_raw: Path, tmp_path: Path) -> None:
    """When the snapshot path's parent directory doesn't exist yet, --update
    should create it rather than crashing with FileNotFoundError."""
    panel = build_indicator_panel(populate_raw)
    z = compute_indicator_z(panel)
    z_dom = compute_domain_z(z)
    comp = compute_composite(z_dom)
    snap = tmp_path / "deep" / "nested" / "fixtures" / "ranking.json"
    assert not snap.parent.exists()
    issues = check_ranking_snapshot(comp, snap, update=True)
    assert not issues
    assert snap.exists()


def test_ranking_snapshot_detects_change(populate_raw: Path, tmp_path: Path) -> None:
    panel = build_indicator_panel(populate_raw)
    z = compute_indicator_z(panel)
    z_dom = compute_domain_z(z)
    comp = compute_composite(z_dom)
    snap = tmp_path / "ranking.json"
    # Write a deliberately-wrong snapshot
    snap.write_text('["ZZZ", "AUS"]')
    issues = check_ranking_snapshot(comp, snap, update=False)
    assert issues, "ranking snapshot check missed a change"
