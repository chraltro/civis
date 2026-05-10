"""Shared pytest fixtures.

We synthesize tiny but realistic raw-source CSVs in a tmp dir so we can run
the full pipeline without hitting the network. The synthetic data is shaped
so the direction-panel tests pass: e.g. on press_freedom (lower=better) the
Nordics should land at the lowest raw values, on life_evaluation (higher=better)
they should land at the highest.

For each indicator we spell out:
  * a "best" group of countries that should land at the indicator's good end
  * a "worst" group that should land at the bad end
  * a default mid-range value for everyone else

Direction-aware filling: best -> low for 'down', high for 'up'; worst flipped.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pipeline.countries import ISO3_LIST
from pipeline.indicators import INDICATORS


@pytest.fixture
def tmp_raw(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    raw.mkdir()
    return raw


# Per-indicator (mid, good_value, bad_value, best_isos, worst_isos).
# good_value is the value assigned to best_isos; bad_value to worst_isos.
# The direction is read from INDICATORS_BY_KEY at fill time.
SYNTH_PROFILES: dict[str, tuple[float, float, float, set[str], set[str]]] = {
    # Material
    "gdp_pc":          (50000, 90000, 35000, {"NOR", "CHE", "USA", "SGP"}, {"PRT", "POL", "EST", "LTU", "CZE"}),
    "household_cons":  (30000, 50000, 18000, {"USA", "CHE", "NOR", "AUS"}, {"EST", "LTU", "POL", "PRT"}),
    "health_pc":       (5000, 12000, 1500, {"USA", "CHE", "NOR", "DEU"}, {"PRT", "POL", "EST", "LTU"}),
    # Health
    "life_expectancy": (81.0, 84.5, 76.0, {"JPN", "CHE", "ESP", "ITA", "ISL"}, {"USA", "POL", "LTU", "EST"}),
    "infant_mort":     (3.0, 1.6, 5.5, {"FIN", "JPN", "ISL", "NOR", "SVN"}, {"USA", "POL", "ISR"}),
    "maternal_mort":   (5.0, 1.5, 22.0, {"NOR", "POL", "ITA", "SWE", "ESP"}, {"USA", "GBR"}),
    # Knowledge
    "schooling":       (12.5, 14.5, 9.5, {"DEU", "USA", "CHE", "GBR"}, {"PRT", "ITA", "ESP"}),
    "tertiary_attain": (40, 60, 22, {"CAN", "KOR", "ISR", "JPN"}, {"ITA", "PRT", "CZE"}),
    "internet_users":  (90, 99, 78, {"DNK", "NOR", "SWE", "ISL"}, {"ITA", "PRT", "POL"}),
    # Safety
    "homicides":       (1.0, 0.2, 6.0, {"SGP", "JPN", "NOR", "CHE", "ITA"}, {"USA", "LTU", "EST"}),
    "suicide":         (10.0, 5.0, 22.0, {"GRC", "ITA", "ISR", "GBR", "ESP"}, {"KOR", "LTU"}),
    # Equality
    "gini":            (32, 24, 41, {"SVN", "CZE", "DNK", "FIN", "BEL"}, {"USA", "GBR"}),
    "gdi":             (0.99, 1.04, 0.97, {"LTU", "EST", "FIN", "POL", "NOR"}, {"USA", "CHE", "ITA"}),
    # Freedom
    "vdem_libdem":     (0.6, 0.88, 0.05, {"NOR", "DNK", "SWE", "FIN", "CHE"}, {"HKG", "POL", "SGP"}),
    "press_freedom":   (25, 6, 78, {"NOR", "FIN", "SWE", "DNK", "NLD"}, {"HKG", "SGP", "ITA"}),
    "corruption":      (70, 90, 40, {"DNK", "FIN", "NZL", "NOR", "SGP"}, {"HKG", "POL", "ITA"}),
    # Work
    "work_hours":      (1700, 1340, 2000, {"DEU", "DNK", "NOR", "NLD", "FRA"}, {"KOR", "SGP", "USA"}),
    "unemployment":    (6, 2.5, 13, {"CZE", "JPN", "POL", "SGP", "KOR"}, {"ESP"}),
    "employment":      (65, 80, 55, {"ISL", "NLD", "NZL", "CHE", "NOR"}, {"ITA", "ESP"}),
    # Environment
    "pm25":            (12, 5, 18, {"FIN", "ISL", "EST", "NZL", "NOR"}, {"POL", "ITA"}),
    "co2_pc":          (8, 4, 16, {"PRT", "FRA", "SWE", "CHE", "ITA"}, {"USA", "AUS"}),
    "renewable":       (25, 80, 11, {"ISL", "NOR", "NZL", "SWE", "DNK"}, {"USA", "JPN", "POL"}),
    # Wellbeing
    "life_eval":       (6.8, 7.8, 5.4, {"FIN", "DNK", "ISL", "SWE", "ISR"}, {"HKG", "KOR"}),
    "adolescent_fert": (5, 1.2, 14, {"KOR", "CHE", "DNK", "JPN", "NLD"}, {"USA", "GBR"}),
    # New indicators
    "broadband":       (35, 50, 18, {"CHE", "FRA", "DNK", "KOR", "NLD"}, {"ITA", "POL", "LTU"}),
    "child_mort":      (3.5, 1.8, 7.0, {"SVN", "FIN", "NOR", "JPN", "ISL"}, {"USA", "POL", "ISR"}),
    "healthy_life_exp":(72, 75, 67, {"JPN", "CHE", "ESP", "ITA", "ISL"}, {"USA", "POL", "LTU"}),
    "research_dev":    (2.5, 4.5, 1.0, {"ISR", "KOR", "USA", "SWE", "JPN"}, {"GRC", "POL", "PRT"}),
    "road_deaths":     (5, 2, 12, {"NOR", "SWE", "CHE", "GBR", "DNK"}, {"USA", "POL", "ITA"}),
    "top_10_income":   (38, 28, 50, {"SVN", "FIN", "DNK", "NLD", "NOR"}, {"USA", "GBR"}),
    "civil_liberties": (0.85, 0.95, 0.5, {"NOR", "DNK", "SWE", "NZL", "FIN"}, {"HKG", "POL", "SGP"}),
    "protected_areas": (15, 35, 5, {"SVN", "DEU", "POL", "GRC", "ESP"}, {"GBR", "USA", "NLD"}),
    "positive_affect": (0.75, 0.85, 0.6, {"ISL", "NZL", "DNK", "NLD", "AUS"}, {"GRC", "KOR", "JPN"}),
}


def _value_for(iso: str, profile: tuple[float, float, float, set[str], set[str]]) -> float:
    mid, good, bad, best, worst = profile
    if iso in best:
        return good
    if iso in worst:
        return bad
    return mid


@pytest.fixture
def populate_raw(tmp_raw: Path) -> Path:
    """Write per-source CSVs with synthetic, direction-correct values.

    Each (iso, year) gets the same value (no time trend) plus a tiny seeded
    noise so values aren't identical (which would otherwise give zero std).
    """
    years = list(range(2010, 2024))
    for ind in INDICATORS:
        prof = SYNTH_PROFILES.get(ind.key)
        if prof is None:
            # No profile defined: fall back to a flat 50 with a tiny noise.
            prof = (50.0, 60.0, 40.0, set(), set())
        for src in ind.sources:
            rows = []
            for iso in ISO3_LIST:
                rng = np.random.default_rng(hash(iso + ind.key) & 0xFFFFFFFF)
                base = _value_for(iso, prof)
                # noise scales with mid so percent-noise stays small
                noise_scale = abs(prof[0]) * 0.001 + 0.01
                for y in years:
                    rows.append(
                        {"iso3": iso, "year": y, "value": base + rng.normal(0, noise_scale)}
                    )
            df = pd.DataFrame(rows)
            name = f"{ind.key}__{src.kind}__{src.ref.replace('/', '_')}.csv"
            df.to_csv(tmp_raw / name, index=False)
    return tmp_raw
