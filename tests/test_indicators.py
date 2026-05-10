"""Manifest-level checks: 24 indicators in 9 domains, no duplicates, etc."""

from __future__ import annotations

from pipeline.indicators import (
    DIRECTION_PANELS,
    DOMAINS,
    INDICATORS,
    INDICATORS_BY_DOMAIN,
    INDICATORS_BY_KEY,
)


def test_indicator_count() -> None:
    assert len(INDICATORS) == 32


def test_domain_count() -> None:
    assert len(DOMAINS) == 9


def test_indicator_keys_unique() -> None:
    keys = [i.key for i in INDICATORS]
    assert len(keys) == len(set(keys)), "duplicate indicator keys"


def test_every_indicator_in_a_known_domain() -> None:
    for i in INDICATORS:
        assert i.domain in DOMAINS, f"{i.key} has unknown domain {i.domain!r}"


def test_every_domain_has_indicators() -> None:
    for d in DOMAINS:
        assert INDICATORS_BY_DOMAIN[d], f"{d} has zero indicators"


def test_indicator_directions_valid() -> None:
    for i in INDICATORS:
        assert i.direction in {"up", "down"}, f"{i.key} has bad direction {i.direction}"


def test_every_indicator_has_at_least_one_source() -> None:
    for i in INDICATORS:
        assert len(i.sources) >= 1, f"{i.key} has no sources"


def test_direction_panels_cover_every_indicator() -> None:
    """validate.check_directions relies on this — flag any holes early."""
    missing = [i.key for i in INDICATORS if i.key not in DIRECTION_PANELS]
    assert not missing, f"DIRECTION_PANELS missing: {missing}"


def test_indicators_by_key_consistent() -> None:
    for i in INDICATORS:
        assert INDICATORS_BY_KEY[i.key] is i
