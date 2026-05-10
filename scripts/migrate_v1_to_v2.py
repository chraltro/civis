"""One-shot migration: schema v1 civis.json + civis.csv -> schema v2 civis.json.

The existing committed civis.csv already carries raw values for every
(iso, year, indicator). This script reads them, plus the existing v1 JSON
(z-scores, domain_z, composite, ranking), and emits a schema v2 JSON with
the new `raw` block and per-indicator display formatting (precision /
prefix / suffix from pipeline.indicators).

Run once after merging the v2 PR so the deployed dashboard shows raw
values immediately, instead of waiting for the next refresh cron.

  python scripts/migrate_v1_to_v2.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from pipeline.countries import ISO3_LIST
from pipeline.indicators import INDICATORS

REPO_ROOT = Path(__file__).resolve().parents[1]
PROCESSED = REPO_ROOT / "data" / "processed"
CSV_PATH = PROCESSED / "civis.csv"
JSON_PATH = PROCESSED / "civis.json"


def main() -> None:
    if not CSV_PATH.exists() or not JSON_PATH.exists():
        raise SystemExit(f"missing {CSV_PATH} or {JSON_PATH}")

    existing = json.loads(JSON_PATH.read_text())
    if existing.get("schema_version", 1) >= 2 and "raw" in existing:
        print("already at schema v2; nothing to do")
        return

    csv = pd.read_csv(CSV_PATH)
    years = existing["years"]
    n_years = len(years)
    year_to_idx = {y: i for i, y in enumerate(years)}

    # Build raw[ind][iso][yi]. Round values to 4 significant figures to keep
    # the JSON small without losing display fidelity.
    def trim(v: float) -> float:
        if v == 0:
            return 0.0
        # Round to a sensible number of decimals: more for small magnitudes,
        # fewer for large. 5 sig figs is plenty for display purposes.
        from math import floor, log10
        digits = max(0, 4 - int(floor(log10(abs(v)))))
        return round(v, min(digits, 6))

    raw: dict[str, dict[str, list[float | None]]] = {
        ind.key: {iso: [None] * n_years for iso in ISO3_LIST} for ind in INDICATORS
    }
    for row in csv.itertuples(index=False):
        ind_key = row.indicator
        if ind_key not in raw:
            continue
        if row.iso3 not in raw[ind_key]:
            continue
        if row.year not in year_to_idx:
            continue
        v = row.value
        if pd.isna(v):
            continue
        raw[ind_key][row.iso3][year_to_idx[row.year]] = trim(float(v))

    # Refresh indicator metadata with display fields
    indicators_meta = [
        {
            "key": i.key,
            "label": i.label,
            "domain": i.domain,
            "direction": i.direction,
            "precision": i.precision,
            "prefix": i.prefix,
            "suffix": i.suffix,
        }
        for i in INDICATORS
    ]

    # Also trim the existing z / domain_z / composite values so the JSON
    # doesn't balloon when we add the raw block.
    def trim_series(arr: list) -> list:
        out_arr = []
        for v in arr:
            if v is None:
                out_arr.append(None)
            else:
                out_arr.append(round(float(v), 3))
        return out_arr

    z_trimmed = {k: {iso: trim_series(s) for iso, s in v.items()} for k, v in existing["z"].items()}
    domain_z_trimmed = {
        d: {iso: trim_series(s) for iso, s in v.items()} for d, v in existing["domain_z"].items()
    }
    composite_trimmed = {iso: trim_series(s) for iso, s in existing["composite"].items()}
    latest_trimmed = {iso: round(float(v), 3) for iso, v in existing["latest"].items()}

    out = {
        "schema_version": 2,
        "generated_at": datetime.now(UTC).isoformat(),
        "years": existing["years"],
        "countries": existing["countries"],
        "domains": existing["domains"],
        "indicators": indicators_meta,
        "z": z_trimmed,
        "raw": raw,
        "domain_z": domain_z_trimmed,
        "composite": composite_trimmed,
        "latest": latest_trimmed,
        "ranked": existing["ranked"],
    }

    JSON_PATH.write_text(json.dumps(out, indent=None, separators=(",", ":")))
    print(f"wrote {JSON_PATH} ({JSON_PATH.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
