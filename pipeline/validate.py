"""Data validation for the Civis Index.

Five families of checks, each runnable independently:

  1. coverage:    every (indicator, country) has at least one real observation
                  between 1990 and YEAR_MAX, otherwise it's silently filled
                  with held-constant values for the entire period.
  2. directions:  for each indicator, the top-3 by latest-period mean must
                  overlap a known-good panel — catches sign flips and rescales.
  3. scale:       merged source distributions must agree to within 5x in median.
  4. invariants:  domain z = mean of indicator z within the domain;
                  composite = mean of domain z.
  5. ranking:     latest 2023 ranking against a snapshot fixture; any change
                  forces an explicit update.

Each check returns ValidationIssue objects rather than raising, so the CLI
can summarize all problems in one pass.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from . import indicators as _indicators_module
from .countries import ISO3_LIST
from .indicators import (
    DIRECTION_PANELS,
    DOMAINS,
    INDICATORS,
    INDICATORS_BY_DOMAIN,
)
from .process import YEARS

log = logging.getLogger(__name__)

Severity = Literal["error", "warn"]


@dataclass
class ValidationIssue:
    check: str
    severity: Severity
    indicator: str | None
    message: str

    def __str__(self) -> str:
        prefix = f"[{self.severity.upper()} {self.check}"
        if self.indicator:
            prefix += f" {self.indicator}"
        prefix += "]"
        return f"{prefix} {self.message}"


# --------------------------------------------------------------------------
# 1. Coverage
# --------------------------------------------------------------------------
def check_coverage(panel: pd.DataFrame) -> list[ValidationIssue]:
    """Every (indicator, country) needs >=1 real observation 1990..YEAR_MAX.

    `panel` here is the *interpolated* indicator panel from process.py, so
    "real" must be inferred. We approximate: a series that is constant for the
    entire period is suspicious and gets flagged. (A single observation
    held-constant produces an exactly-constant series; multiple observations
    interpolated do not.)
    """
    issues: list[ValidationIssue] = []
    for ind in INDICATORS:
        if ind.key not in panel.columns:
            continue
        for iso in ISO3_LIST:
            if (iso, YEARS[0]) not in panel.index:
                continue
            sub = panel.xs(iso, level="iso3")[ind.key]
            n_present = sub.notna().sum()
            if n_present == 0:
                issues.append(ValidationIssue(
                    check="coverage",
                    severity="warn",
                    indicator=ind.key,
                    message=f"{iso} has zero observations across {YEARS[0]}..{YEARS[-1]}",
                ))
                continue
            unique = sub.dropna().unique()
            if len(unique) == 1 and n_present == len(YEARS):
                issues.append(ValidationIssue(
                    check="coverage",
                    severity="warn",
                    indicator=ind.key,
                    message=(
                        f"{iso}: identical value held constant across all "
                        f"{len(YEARS)} years (single observation, possibly "
                        f"missing time series)"
                    ),
                ))
    return issues


# --------------------------------------------------------------------------
# 2. Directions
# --------------------------------------------------------------------------
def check_directions(panel: pd.DataFrame) -> list[ValidationIssue]:
    """Best-3 by 5-year tail mean must overlap a known-good panel."""
    issues: list[ValidationIssue] = []
    tail_years = [y for y in YEARS if y >= YEARS[-1] - 4]
    for ind in INDICATORS:
        if ind.key not in panel.columns:
            continue
        # Compute country mean over tail
        sub = panel[ind.key].unstack("year")
        if sub.empty:
            continue
        tail = sub[tail_years].mean(axis=1, skipna=True)
        # Direction-aware "best": for 'up' indicators we want largest values;
        # for 'down', smallest.
        if ind.direction == "up":
            top = tail.nlargest(5).index.tolist()
        else:
            top = tail.nsmallest(5).index.tolist()
        panel_iso = DIRECTION_PANELS.get(ind.key)
        if not panel_iso:
            continue
        # Restrict expected panel to ones present in our 29-country set so we
        # don't penalize against absent reference countries.
        candidates = panel_iso & set(ISO3_LIST)
        if not candidates:
            continue
        if not any(iso in candidates for iso in top[:3]):
            issues.append(ValidationIssue(
                check="directions",
                severity="error",
                indicator=ind.key,
                message=(
                    f"top-3 {top[:3]} contains none of {sorted(candidates)} "
                    f"(direction='{ind.direction}'). possible sign flip or scale bug."
                ),
            ))
    return issues


# --------------------------------------------------------------------------
# 3. Scale
# --------------------------------------------------------------------------
def check_scale_mismatch(raw_dir: Path) -> list[ValidationIssue]:
    """If an indicator has multiple sources, their medians shouldn't differ >5x."""
    issues: list[ValidationIssue] = []
    # Read INDICATORS via the module so monkey-patched test fixtures are seen.
    for ind in _indicators_module.INDICATORS:
        if len(ind.sources) < 2:
            continue
        medians: list[tuple[str, float]] = []
        for src in ind.sources:
            name = f"{ind.key}__{src.kind}__{src.ref.replace('/', '_')}.csv"
            p = raw_dir / name
            if not p.exists():
                continue
            df = pd.read_csv(p)
            if df.empty:
                continue
            m = float(np.nanmedian(df["value"].astype(float)))
            medians.append((f"{src.kind}:{src.ref}", m))
        if len(medians) < 2:
            continue
        nonzero = [m for _, m in medians if m and abs(m) > 0]
        if len(nonzero) < 2:
            continue
        ratio = max(abs(m) for m in nonzero) / max(min(abs(m) for m in nonzero), 1e-9)
        if ratio > 5.0:
            issues.append(ValidationIssue(
                check="scale",
                severity="error",
                indicator=ind.key,
                message=f"source medians differ {ratio:.1f}x: {medians}",
            ))
    return issues


# --------------------------------------------------------------------------
# 4. Aggregation invariants
# --------------------------------------------------------------------------
def check_invariants(
    z_indicators: pd.DataFrame,
    z_domains: pd.DataFrame,
    composite: pd.DataFrame,
    *,
    tol: float = 1e-9,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    # Domain = mean of available indicator z within the domain
    for d in DOMAINS:
        keys = [i.key for i in INDICATORS_BY_DOMAIN[d] if i.key in z_indicators.columns]
        if not keys:
            continue
        recomputed = z_indicators[keys].mean(axis=1, skipna=True)
        diff = (recomputed - z_domains[d]).abs().max(skipna=True)
        if pd.notna(diff) and diff > tol:
            issues.append(ValidationIssue(
                check="invariants",
                severity="error",
                indicator=None,
                message=f"domain '{d}' aggregation drift: max |diff|={diff}",
            ))
    # Composite = mean of domain z
    recomputed = z_domains.mean(axis=1, skipna=True)
    diff = (recomputed - composite["composite"]).abs().max(skipna=True)
    if pd.notna(diff) and diff > tol:
        issues.append(ValidationIssue(
            check="invariants",
            severity="error",
            indicator=None,
            message=f"composite aggregation drift: max |diff|={diff}",
        ))
    return issues


# --------------------------------------------------------------------------
# 5. Ranking snapshot
# --------------------------------------------------------------------------
def check_ranking_snapshot(
    composite: pd.DataFrame,
    snapshot_path: Path,
    *,
    update: bool = False,
) -> list[ValidationIssue]:
    """Compare latest-year ranking against a fixture; flag any change."""
    latest_idx = (composite.reset_index()
                  .groupby("iso3")["year"].idxmax())
    latest = composite.iloc[latest_idx.values].reset_index()
    latest = latest.sort_values("composite", ascending=False)
    ranking = latest["iso3"].tolist()
    if not snapshot_path.exists():
        if update:
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text(json.dumps(ranking, indent=2))
            return []
        return [ValidationIssue(
            check="ranking",
            severity="warn",
            indicator=None,
            message=f"no snapshot at {snapshot_path}; pass --update-snapshot to create.",
        )]
    expected = json.loads(snapshot_path.read_text())
    if ranking != expected:
        if update:
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text(json.dumps(ranking, indent=2))
            return []
        diffs = [
            f"{iso}: {expected.index(iso) + 1} -> {ranking.index(iso) + 1}"
            for iso in ranking if iso in expected and ranking.index(iso) != expected.index(iso)
        ]
        return [ValidationIssue(
            check="ranking",
            severity="error",
            indicator=None,
            message="latest ranking changed; pass --update-snapshot to accept. "
                    f"diffs: {diffs[:10]}",
        )]
    return []


# --------------------------------------------------------------------------
# Aggregate runner
# --------------------------------------------------------------------------
def run_all(
    *,
    raw_dir: Path,
    panel: pd.DataFrame,
    z_indicators: pd.DataFrame,
    z_domains: pd.DataFrame,
    composite: pd.DataFrame,
    snapshot_path: Path,
    update_snapshot: bool = False,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    issues += check_coverage(panel)
    issues += check_directions(panel)
    issues += check_scale_mismatch(raw_dir)
    issues += check_invariants(z_indicators, z_domains, composite)
    issues += check_ranking_snapshot(composite, snapshot_path, update=update_snapshot)
    return issues


__all__ = [
    "ValidationIssue",
    "check_coverage",
    "check_directions",
    "check_scale_mismatch",
    "check_invariants",
    "check_ranking_snapshot",
    "run_all",
]
