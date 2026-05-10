#!/usr/bin/env bash
# Manual refresh: fetch + process + validate, with snapshot.
# Equivalent to the weekly cron workflow but runs locally.
#
# Usage:
#   scripts/refresh_data.sh                # standard: fail on ranking change
#   scripts/refresh_data.sh --update-snapshot   # accept changes

set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  uv venv --python 3.11
  uv pip install -e ".[dev]"
fi

source .venv/bin/activate

civis fetch
civis process --snapshot

if [ "${1:-}" = "--update-snapshot" ]; then
  civis validate --update-snapshot
else
  civis validate
fi

echo "Refresh complete. data/processed/civis.json is up to date."
