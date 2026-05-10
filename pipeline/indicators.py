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
    # WB API "source" parameter. The default catalog doesn't include WGI
    # (Worldwide Governance Indicators); those need source=23. None = default.
    wb_source: int | None = None


@dataclass(frozen=True)
class Indicator:
    key: str
    label: str
    domain: str
    direction: Direction
    sources: tuple[Source, ...]
    notes: str = ""
    # Display formatting for raw values (web reads these from civis.json).
    # final = f"{prefix}{value:.{precision}f}{suffix}", with thousands sep on
    # the integer part by the web layer.
    precision: int = 1
    prefix: str = ""
    suffix: str = ""


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
        precision=0, prefix="$",
    ),
    Indicator(
        key="household_cons",
        label="Household consumption per capita",
        domain="Material",
        direction="up",
        sources=(Source("wb", "NE.CON.PRVT.PC.KD"),),
        precision=0, prefix="$",
    ),
    # health_pc was dropped: per-capita health spending with direction=up
    # rewards systems that pay more for the same outcome (USA spends 2x other
    # OECD countries with worse outcomes). Health *outcomes* are captured by
    # the Health domain (life expectancy, infant/maternal/child mortality).
    Indicator(
        key="broadband",
        label="Fixed broadband subs (per 100)",
        domain="Material",
        direction="up",
        sources=(Source("wb", "IT.NET.BBND.P2"),),
        precision=1,
    ),

    # ------------------ Health ------------------
    Indicator(
        key="life_expectancy",
        label="Life expectancy at birth",
        domain="Health",
        direction="up",
        sources=(Source("wb", "SP.DYN.LE00.IN"),),
        precision=1, suffix=" yrs",
    ),
    Indicator(
        key="infant_mort",
        label="Infant mortality (per 1,000)",
        domain="Health",
        direction="down",
        sources=(Source("wb", "SP.DYN.IMRT.IN"),),
        precision=1,
    ),
    Indicator(
        key="maternal_mort",
        label="Maternal mortality (per 100k)",
        domain="Health",
        direction="down",
        sources=(Source("wb", "SH.STA.MMRT"),),
        precision=0,
    ),
    Indicator(
        key="child_mort",
        label="Under-5 mortality (per 1k)",
        domain="Health",
        direction="down",
        sources=(Source("wb", "SH.DYN.MORT"),),
        precision=1,
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
        precision=1, suffix=" yrs",
    ),
    Indicator(
        key="tertiary_attain",
        label="Tertiary attainment, 25+",
        domain="Knowledge",
        direction="up",
        sources=(Source("wb", "SE.TER.CUAT.BA.ZS"),),
        precision=0, suffix="%",
    ),
    Indicator(
        key="internet_users",
        label="Internet users",
        domain="Knowledge",
        direction="up",
        sources=(Source("wb", "IT.NET.USER.ZS"),),
        precision=0, suffix="%",
    ),
    Indicator(
        key="research_dev",
        label="R&D spending",
        domain="Knowledge",
        direction="up",
        sources=(Source("wb", "GB.XPD.RSDV.GD.ZS"),),
        precision=2, suffix="% GDP",
    ),

    # ------------------ Safety ------------------
    Indicator(
        key="homicides",
        label="Homicide rate",
        domain="Safety",
        direction="down",
        sources=(Source("wb", "VC.IHR.PSRC.P5"),),
        precision=2, suffix=" / 100k",
    ),
    Indicator(
        key="suicide",
        label="Suicide rate",
        domain="Safety",
        direction="down",
        sources=(Source("wb", "SH.STA.SUIC.P5"),),
        precision=1, suffix=" / 100k",
    ),
    Indicator(
        key="road_deaths",
        label="Road traffic deaths",
        domain="Safety",
        direction="down",
        sources=(Source("wb", "SH.STA.TRAF.P5"),),
        precision=1, suffix=" / 100k",
    ),
    Indicator(
        key="political_stability",
        label="Political stability (WGI)",
        domain="Safety",
        direction="up",
        sources=(
            # WGI indicators (PV/VA/GE/RQ/RL/CC) live under WB API source=23.
            # Without that param the API returns a no-data envelope.
            Source("wb", "PV.EST", wb_source=23),
        ),
        notes=(
            "World Bank's Worldwide Governance Indicators: Political Stability "
            "and Absence of Violence/Terrorism, estimate (-2.5 worst, +2.5 best). "
            "Captures perceived likelihood of conflict, terrorism, and politically-"
            "motivated violence. Distinguishes safe-feeling-but-conflict-adjacent "
            "places (Israel, Korea historically) from civilian-violence-low-and-"
            "stable places (Nordics, NL)."
        ),
        precision=2,
    ),
    # safe_walking was dropped: all three OWID slug candidates 404'd. Without
    # network access to probe OWID's current chart pages from the build
    # sandbox, blind-guessing more slugs would just burn CI. Track as a
    # follow-up issue if/when someone confirms the working slug.

    # ------------------ Equality ------------------
    Indicator(
        key="gini",
        label="Income Gini (post-tax)",
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
        precision=1,
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
        precision=3,
    ),
    Indicator(
        key="top_10_income",
        label="Top 10% income share",
        domain="Equality",
        direction="down",
        sources=(Source("wb", "SI.DST.10TH.10"),),
        precision=1, suffix="%",
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
        precision=2,
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
        precision=1,
    ),
    Indicator(
        key="corruption",
        label="Anti-corruption (CPI)",
        domain="Freedom",
        direction="up",
        sources=(
            Source(
                "owid",
                "corruption-perception-index",
                column=("corruption_perception_index", "cpi_score"),
            ),
        ),
        precision=0,
    ),
    Indicator(
        key="civil_liberties",
        label="Human rights (V-Dem)",
        domain="Freedom",
        direction="up",
        sources=(
            # OWID redirected `civil-liberties-index-vdem` -> this slug; using
            # the destination directly so we don't depend on the redirect.
            # V-Dem's human-rights index is the consolidated civil-liberties
            # measure (freedom of expression, association, person, due process).
            Source(
                "owid",
                "human-rights-index-vdem",
                column=("human_rights_index", "v2x_civlib", "civil_liberties_index"),
            ),
        ),
        precision=2,
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
        precision=0, suffix=" hrs",
    ),
    Indicator(
        key="unemployment",
        label="Unemployment rate",
        domain="Work",
        direction="down",
        sources=(Source("wb", "SL.UEM.TOTL.ZS"),),
        precision=1, suffix="%",
    ),
    Indicator(
        key="employment",
        label="Employment-to-population ratio (15+)",
        domain="Work",
        direction="up",
        sources=(Source("wb", "SL.EMP.TOTL.SP.ZS"),),
        precision=0, suffix="%",
    ),

    # ------------------ Environment ------------------
    Indicator(
        key="pm25",
        label="PM2.5 air pollution",
        domain="Environment",
        direction="down",
        sources=(Source("wb", "EN.ATM.PM25.MC.M3"),),
        precision=1, suffix=" µg/m³",
    ),
    Indicator(
        key="co2_pc",
        label="CO₂ emissions per capita",
        domain="Environment",
        direction="down",
        sources=(
            Source(
                "owid",
                "co-emissions-per-capita",
                column=("annual_co_emissions_per_capita", "co2_per_capita"),
            ),
        ),
        precision=1, suffix=" t",
    ),
    Indicator(
        key="renewable",
        label="Renewable energy share",
        domain="Environment",
        direction="up",
        sources=(
            Source(
                "owid",
                "renewable-share-energy",
                column=("renewables_share_energy", "renewable_share_energy"),
            ),
        ),
        precision=0, suffix="%",
    ),
    Indicator(
        key="protected_areas",
        label="Terrestrial protected areas",
        domain="Environment",
        direction="up",
        sources=(Source("wb", "ER.LND.PTLD.ZS"),),
        precision=1, suffix="% land",
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
        precision=2,
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
        precision=1, suffix=" / 1k",
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
    # health_pc dropped (was direction=up which incorrectly rewarded high spend)
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
    # Phase 2 additions
    "broadband":        frozenset({"CHE", "FRA", "DNK", "KOR", "NLD", "NOR", "DEU", "ISL"}),
    "child_mort":       frozenset({"SVN", "FIN", "NOR", "JPN", "ISL", "EST", "SWE", "SGP"}),
    "research_dev":     frozenset({"ISR", "KOR", "USA", "SWE", "JPN", "CHE", "BEL", "DEU"}),
    "road_deaths":      frozenset({"NOR", "SWE", "CHE", "GBR", "DNK", "DEU", "NLD", "ISL"}),
    "top_10_income":    frozenset({"SVN", "FIN", "DNK", "NLD", "NOR", "BEL", "SWE", "CZE"}),
    "civil_liberties":  frozenset({"NOR", "DNK", "SWE", "NZL", "FIN", "CHE", "NLD", "DEU"}),
    "political_stability": frozenset({"NOR", "ISL", "FIN", "SWE", "NZL", "CHE", "SGP", "DNK"}),
    "protected_areas":  frozenset({"SVN", "DEU", "POL", "GRC", "ESP", "FRA", "GBR", "ITA"}),
}
