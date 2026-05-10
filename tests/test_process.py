"""Tests for pipeline.process: interpolation, z-scoring, aggregation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pipeline.indicators import DOMAINS, INDICATORS, INDICATORS_BY_DOMAIN
from pipeline.process import (
    WINSOR_LIMIT,
    YEARS,
    _interpolate_country,
    build_indicator_panel,
    compute_composite,
    compute_domain_z,
    compute_indicator_z,
)


# --------------------------------------------------------------------------
# Interpolation
# --------------------------------------------------------------------------
def test_interp_holds_constant_outside_observed_range() -> None:
    obs = pd.Series({2000: 10.0, 2010: 20.0})
    out = _interpolate_country(obs, list(range(1995, 2016)))
    # Linear inside
    assert out[2005] == pytest.approx(15.0)
    # Constant before first
    assert out[1995] == 10.0
    # Constant after last
    assert out[2015] == 20.0


def test_interp_handles_all_nan() -> None:
    obs = pd.Series([np.nan, np.nan], index=[2000, 2010])
    out = _interpolate_country(obs, list(range(2000, 2011)))
    assert out.isna().all()


def test_interp_single_observation_holds_constant() -> None:
    obs = pd.Series({2005: 42.0})
    out = _interpolate_country(obs, list(range(2000, 2011)))
    assert (out == 42.0).all()


# --------------------------------------------------------------------------
# Z-scoring + winsorization
# --------------------------------------------------------------------------
def test_zscore_is_panel_wide(populate_raw: Path) -> None:
    panel = build_indicator_panel(populate_raw)
    z = compute_indicator_z(panel)
    # Across the whole panel for any indicator, mean should be ~0 (ignoring
    # winsorization edges) and std should be ~1 (subject to winsorization).
    for col in z.columns:
        s = z[col].dropna()
        if len(s) < 30:
            continue
        # winsorization at ±2.5σ can bias the mean by up to ~0.1 when the
        # tails are asymmetric, so we use a generous tolerance here.
        assert abs(s.mean()) < 0.15, f"{col} mean not ~0: {s.mean()}"


def test_winsorization_caps_at_2_5_sigma(populate_raw: Path) -> None:
    panel = build_indicator_panel(populate_raw)
    z = compute_indicator_z(panel)
    assert z.max().max() <= WINSOR_LIMIT + 1e-9
    assert z.min().min() >= -WINSOR_LIMIT - 1e-9


def test_down_indicator_signs_flipped(populate_raw: Path) -> None:
    """For a 'down' indicator, low raw values should produce high z-scores."""
    panel = build_indicator_panel(populate_raw)
    z = compute_indicator_z(panel)
    # press_freedom is 'down' (lower=freer). NOR has lowest raw value in our
    # synthetic data, so should have the *highest* z.
    s = z["press_freedom"]
    nor_mean = s.xs("NOR", level="iso3").mean()
    # average across other countries
    others_mean = s.drop("NOR", level="iso3").mean()
    assert nor_mean > others_mean, "down-direction sign flip not applied"


# --------------------------------------------------------------------------
# Aggregation invariants
# --------------------------------------------------------------------------
def test_domain_z_equals_mean_of_indicator_z(populate_raw: Path) -> None:
    panel = build_indicator_panel(populate_raw)
    z = compute_indicator_z(panel)
    z_dom = compute_domain_z(z)
    for d in DOMAINS:
        keys = [i.key for i in INDICATORS_BY_DOMAIN[d] if i.key in z.columns]
        recomputed = z[keys].mean(axis=1, skipna=True)
        diff = (recomputed - z_dom[d]).abs().max()
        assert pd.isna(diff) or diff < 1e-9


def test_composite_equals_mean_of_domain_z(populate_raw: Path) -> None:
    panel = build_indicator_panel(populate_raw)
    z = compute_indicator_z(panel)
    z_dom = compute_domain_z(z)
    comp = compute_composite(z_dom)
    recomputed = z_dom.mean(axis=1, skipna=True)
    diff = (recomputed - comp["composite"]).abs().max()
    assert pd.isna(diff) or diff < 1e-9


# --------------------------------------------------------------------------
# Panel shape
# --------------------------------------------------------------------------
def test_panel_has_all_countries_and_years(populate_raw: Path) -> None:
    panel = build_indicator_panel(populate_raw)
    isos = set(panel.index.get_level_values("iso3"))
    years = set(panel.index.get_level_values("year"))
    from pipeline.countries import ISO3_LIST
    assert isos == set(ISO3_LIST)
    assert years == set(YEARS)


def test_panel_columns_are_indicator_keys(populate_raw: Path) -> None:
    panel = build_indicator_panel(populate_raw)
    expected = {i.key for i in INDICATORS}
    assert set(panel.columns) == expected
