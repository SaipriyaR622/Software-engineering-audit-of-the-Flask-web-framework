#!/usr/bin/env bash
# Step 7: generate UML class and package diagrams with pyreverse (part of pylint).
# Needs Graphviz installed for PNG output (apt install graphviz / brew install graphviz).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${1:-$ROOT/target}"
OUT="$ROOT/results/uml"
mkdir -p "$OUT"

echo "Generating UML diagrams..."
cd "$TARGET/src"
# Core classes only, so the diagram stays readable.
pyreverse -o png -p flask_core --only-classnames --filter-mode PUB_ONLY \
  -d "$OUT" flask/sansio/scaffold.py flask/sansio/app.py flask/app.py \
  flask/sansio/blueprints.py flask/blueprints.py flask/ctx.py flask/sessions.py
# Package (module dependency) diagram for the whole package.
pyreverse -o png -p flask_all -d "$OUT" flask
echo "  wrote results/uml/"
