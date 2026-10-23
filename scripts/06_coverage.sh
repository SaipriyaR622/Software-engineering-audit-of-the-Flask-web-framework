#!/usr/bin/env bash
# Step 6: run Flask's own test suite with coverage.
# Requires Flask installed in editable mode (see README).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${1:-$ROOT/target}"
mkdir -p "$ROOT/results"

echo "Running Flask test suite with coverage..."
cd "$TARGET"
python -m pytest -q -p no:cacheprovider \
  --cov=flask --cov-branch \
  --cov-report=json:"$ROOT/results/coverage.json" \
  --cov-report=term \
  --junitxml="$ROOT/results/tests_junit.xml" \
  tests | tee "$ROOT/results/coverage_terminal.txt"
