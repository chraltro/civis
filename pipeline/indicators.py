"""Indicator definitions for the Civis Index.

24 indicators across 9 equally-weighted domains. Each indicator has:
  - key:        unique short identifier
  - label:      human-readable label
  - domain:     one of the 9 domains
  - direction:  "up" if higher is better, "down" if lower is better
  - sources:    ordered list of fetcher specs; first non-empty observation wins,
                with later entries used as fallback. Each source carries the
                expected scale so cross-source merges can sanity-check.

The domain order in DOMAINS controls dashboard display order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Direction = Literal["up", "down"]

DOMAINS: tuple[str, ...] = (
    "Material",
    "Health",
    "Knowledge",
    "Safety",
    "Equality",
    "Freedom",
    "Work",
    "Environment",
    "Wellbeing",
)


@dataclass(frozen=True)
class Source:
    """Where to fetch one observation series for an indicator."""
    kind: Literal["wb", "owid"]
    # WB indicator code (e.g. "NY.GDP.PCAP.PP.KD") OR OWID grapher slug.
    ref: str
    # Column name within the OWID CSV that carries the value, OR None for WB
    # (WB API returns a fixed shape, no column choice). For OWID, this can be
    # a tuple of candidate column names to try in order — the fetcher discovers
    # which is present.
    column: str | tuple[str, ...] | None = None
    # Multiplier to apply on raw values to align with the canonical scale.
    # E.g. LIS Gini is 0..1; WB Gini is 0..100; if you fetch LIS but want WB
    # scale you'd set scale=100.
    scale: float = 1.0
    # Lower bound of plausible values (after scale). Sanity check.
    plausible_min: float | None = None
    plausible_max: float | None = None


@dataclass(frozen=True)
class Indicator:
    key: str
    label: str
    domain: str
    direction: Direction
    sources: tuple[Source, ...]
    notes: str = ""


# --------------------------------------------------------------------------
# Indicator manifest
# --------------------------------------------------------------------------
# OWID slugs verified against ourworldindata.org/grapher/{slug}.csv as of 2026-05.
# Multiple candidate column names are listed because OWID renames columns
# between snapshots; the fetcher discovers which one is actually present.

INDICATORS: tuple[Indicator, ...] = (
    # ------------------ Material ------------------
    Indicator(
        key="gdp_pc",
        label="GDP per capita (PPP)",
        domain="Material",
        direction="up",
        sources=(Source("wb", "NY.GDP.PCAP.PP.KD"),),
    ),
    Indicator(
        key="household_cons",
        label="Household consumption per capita",
        domain="Material",
        direction="up",
        sources=(Source("wb", "NE.CON.PRVT.PC.KD"),),
    ),
    Indicator(
        key="health_pc",
        label="Health spending per capita",
        domain="Material",
        direction="up",
        sources=(Source("wb", "SH.XPD.CHEX.PC.CD"),),
    ),

    # ------------------ Health ------------------
    Indicator(
        key="life_expectancy",
        label="Life expectancy at birth",
        domain="Health",
        direction="up",
        sources=(Source("wb", "SP.DYN.LE00.IN"),),
    ),
    Indicator(
        key="infant_mort",
        label="Infant mortality (per 1,000)",
        domain="Health",
        direction="down",
        sources=(Source("wb", "SP.DYN.IMRT.IN"),),
    ),
    Indicator(
        key="maternal_mort",
        label="Maternal mortality (per 100k)",
        domain="Health",
        direction="down",
        sources=(Source("wb", "SH.STA.MMRT"),),
    ),

    # ------------------ Knowledge ------------------
    Indicator(
        key="schooling",
        label="Mean years of schooling",
        domain="Knowledge",
        direction="up",
        sources=(
            Source(
                "owid",
                "mean-years-of-schooling-long-run",
                column=("mean_years_of_schooling", "average_years_of_schooling"),
            ),
        ),
    ),
    Indicator(
        key="tertiary_attain",
        label="Tertiary attainment, 25+ (%)",
        domain="Knowledge",
        direction="up",
        sources=(Source("wb", "SE.TER.CUAT.BA.ZS"),),
    ),
    Indicator(
        key="internet_users",
        label="Internet users (% population)",
        domain="Knowledge",
        direction="up",
        sources=(Source("wb", "IT.NET.USER.ZS"),),
    ),

    # ------------------ Safety ------------------
    Indicator(
        key="homicides",
        label="Homicide rate (per 100k)",
        domain="Safety",
        direction="down",
        sources=(Source("wb", "VC.IHR.PSRC.P5"),),
    ),
    Indicator(
        key="suicide",
        label="Suicide rate (per 100k)",
        domain="Safety",
        direction="down",
        sources=(Source("wb", "SH.STA.SUIC.P5"),),
    ),

    # ------------------ Equality ------------------
    Indicator(
        key="gini",
        label="Income Gini (post-tax, 0–100)",
        domain="Equality",
        direction="down",
        sources=(
            # World Bank PIP: 0..100 scale (or sometimes 0..1; we plausibility-check)
            Source("wb", "SI.POV.GINI"),
        ),
        notes=(
            "World Bank PIP Gini is reported on a 0..100 scale, but some legacy "
            "feeds (LIS) use 0..1. The merge layer rescales by 100x if it detects "
            "a sub-1.0 series."
        ),
    ),
    Indicator(
        key="gdi",
        label="Gender Development Index",
        domain="Equality",
        direction="up",
        sources=(
            Source(
                "owid",
                "gender-development-index",
                column=("gender_development_index",),
            ),
        ),
        notes=(
            "GDI close to 1.0 = most equal. Treated as monotonic 'up' here, which "
            "is approximately correct for our 29-country panel since most values "
            "are <= 1.0. Open issue: consider folding as 1 - |1 - GDI|."
        ),
    ),

    # ------------------ Freedom ------------------
    Indicator(
        key="vdem_libdem",
        label="Liberal democracy (V-Dem)",
        domain="Freedom",
        direction="up",
        sources=(
            Source(
                "owid",
                "liberal-democracy-index",
                column=("liberal_democracy_index", "libdem_vdem_owid"),
            ),
        ),
    ),
    Indicator(
        key="press_freedom",
        label="Press freedom (RSF, lower=freer, pre-2022 methodology)",
        domain="Freedom",
        direction="down",
        sources=(
            # OWID has reorganized this dataset multiple times. Try the most
            # recent slug first, fall back to historical names. The fetcher
            # uses the first source that returns data; failures of fallbacks
            # don't abort the run.
            Source(
                "owid",
                "press-freedom-rsf",
                column=("press_freedom_score", "rsf_press_freedom_index", "score"),
            ),
            Source(
                "owid",
                "rsf-press-freedom-index",
                column=("press_freedom_score", "rsf_press_freedom_index", "score"),
            ),
            Source(
                "owid",
                "press-freedom-index",
                column=("press_freedom_score", "rsf_press_freedom_index", "score"),
            ),
        ),
        notes=(
            "RSF changed methodology in 2022 to a 0..100 'higher is better' "
            "score. The pre-2022 series is 'lower is better' — direction='down'. "
            "If you upgrade to the post-2022 series, flip the direction and "
            "update the test panel."
        ),
    ),
    Indicator(
        key="corruption",
        label="Anti-corruption (CPI, higher=cleaner)",
        domain="Freedom",
        direction="up",
        sources=(
            Source(
                "owid",
                "corruption-perception-index",
                column=("corruption_perception_index", "cpi_score"),
            ),
        ),
    ),

    # ------------------ Work ------------------
    Indicator(
        key="work_hours",
        label="Annual working hours per worker",
        domain="Work",
        direction="down",
        sources=(
            Source(
                "owid",
                "annual-working-hours-per-worker",
                column=("annual_working_hours_per_worker", "average_annual_hours_worked"),
            ),
        ),
    ),
    Indicator(
        key="unemployment",
        label="Unemployment rate (%)",
        domain="Work",
        direction="down",
        sources=(Source("wb", "SL.UEM.TOTL.ZS"),),
    ),
    Indicator(
        key="employment",
        label="Employment-to-population ratio (15+)",
        domain="Work",
        direction="up",
        sources=(Source("wb", "SL.EMP.TOTL.SP.ZS"),),
    ),

    # ------------------ Environment ------------------
    Indicator(
        key="pm25",
        label="PM2.5 air pollution (µg/m³)",
        domain="Environment",
        direction="down",
        sources=(Source("wb", "EN.ATM.PM25.MC.M3"),),
    ),
    Indicator(
        key="co2_pc",
        label="CO₂ emissions per capita (t)",
        domain="Environment",
        direction="down",
        sources=(
            Source(
                "owid",
                "co-emissions-per-capita",
                column=("annual_co_emissions_per_capita", "co2_per_capita"),
            ),
        ),
    ),
    Indicator(
        key="renewable",
        label="Renewable energy share (%)",
        domain="Environment",
        direction="up",
        sources=(
            Source(
                "owid",
                "renewable-share-energy",
                column=("renewables_share_energy", "renewable_share_energy"),
            ),
        ),
    ),

    # ------------------ Wellbeing ------------------
    Indicator(
        key="life_eval",
        label="Life evaluation (Cantril ladder)",
        domain="Wellbeing",
        direction="up",
        sources=(
            Source(
                "owid",
                "happiness-cantril-ladder",
                column=(
                    "cantril_ladder_score",
                    "life_satisfaction",
                    "happiness_score_world_happiness_report",
                ),
            ),
        ),
    ),
    Indicator(
        key="adolescent_fert",
        label="Adolescent fertility rate (per 1k)",
        domain="Wellbeing",
        direction="down",
        sources=(Source("wb", "SP.ADO.TFRT"),),
        notes=(
            "Placed in Wellbeing as a proxy for life-trajectory autonomy. "
            "Defensible but contested. Could move to Health or Equality."
        ),
    ),
)


INDICATORS_BY_KEY: dict[str, Indicator] = {i.key: i for i in INDICATORS}
INDICATORS_BY_DOMAIN: dict[str, list[Indicator]] = {d: [] for d in DOMAINS}
for _i in INDICATORS:
    INDICATORS_BY_DOMAIN[_i.domain].append(_i)


# Direction sanity panels: for each indicator, when ranked best-to-worst across
# 2018-2023 means, the top-3 should overlap this set. validate.py uses this to
# detect direction flips and scale errors automatically.
DIRECTION_PANELS: dict[str, frozenset[str]] = {
    "gdp_pc":           frozenset({"NOR", "CHE", "USA", "SGP", "IRL", "LUX"}),  # IRL/LUX not in panel; stays as ref
    "household_cons":   frozenset({"USA", "CHE", "NOR", "AUS"}),
    "health_pc":        frozenset({"USA", "CHE", "NOR", "DEU"}),
    "life_expectancy":  frozenset({"JPN", "CHE", "ESP", "ITA", "NOR", "ISL", "AUS", "KOR"}),
    "infant_mort":      frozenset({"FIN", "ISL", "JPN", "NOR", "SWE", "SVN", "EST"}),
    "maternal_mort":    frozenset({"NOR", "POL", "ITA", "SWE", "ISR", "ESP", "DNK"}),
    "schooling":        frozenset({"DEU", "USA", "CHE", "GBR", "ISL", "AUS", "NOR"}),
    "tertiary_attain":  frozenset({"CAN", "KOR", "ISR", "JPN", "GBR", "USA", "LTU"}),
    "internet_users":   frozenset({"DNK", "NOR", "SWE", "ISL", "NLD", "FIN", "GBR"}),
    "homicides":        frozenset({"SGP", "JPN", "NOR", "ITA", "CHE", "KOR", "POL", "ESP", "AUT"}),
    "suicide":          frozenset({"GRC", "ITA", "ISR", "ESP", "GBR", "SGP", "NLD", "PRT"}),
    "gini":             frozenset({"SVN", "CZE", "DNK", "FIN", "BEL", "NOR", "SWE", "ISL", "POL"}),
    "gdi":              frozenset({"LTU", "EST", "FIN", "POL", "NOR", "SWE", "FRA", "DNK"}),
    "vdem_libdem":      frozenset({"NOR", "DNK", "SWE", "FIN", "CHE", "DEU", "NZL", "EST"}),
    "press_freedom":    frozenset({"NOR", "FIN", "SWE", "DNK", "NLD", "ISL", "EST", "PRT"}),
    "corruption":       frozenset({"DNK", "FIN", "NZL", "NOR", "SGP", "SWE", "CHE", "NLD"}),
    "work_hours":       frozenset({"DEU", "DNK", "NOR", "NLD", "FRA", "SWE", "CHE", "FIN"}),
    "unemployment":     frozenset({"CZE", "ISL", "JPN", "POL", "SGP", "KOR", "DEU", "CHE", "NLD"}),
    "employment":       frozenset({"ISL", "NLD", "NZL", "CHE", "NOR", "SWE", "EST", "JPN"}),
    "pm25":             frozenset({"FIN", "ISL", "EST", "NZL", "NOR", "AUS", "SWE", "CAN"}),
    "co2_pc":           frozenset({"PRT", "FRA", "SWE", "CHE", "ITA", "ESP", "GBR", "DEU", "LTU"}),
    "renewable":        frozenset({"ISL", "NOR", "NZL", "SWE", "DNK", "AUT", "FIN", "PRT"}),
    "life_eval":        frozenset({"FIN", "DNK", "ISL", "SWE", "ISR", "NLD", "NOR", "CHE"}),
    "adolescent_fert":  frozenset({"KOR", "CHE", "DNK", "JPN", "NLD", "ITA", "NOR", "SGP", "SWE"}),
}
