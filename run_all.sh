#!/usr/bin/env bash
# Run the whole Flask SE audit pipeline.
# Usage: ./run_all.sh            (clones Flask into ./target if missing)
#        ./run_all.sh /path/to/flask
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
TARGET="${1:-$ROOT/target}"
# Pin to the commit analysed in the report so numbers are reproducible.
PINNED_COMMIT="d086db856be187255b8ec61ef409357393020f32"

if [ ! -d "$TARGET/.git" ]; then
  echo "Cloning Flask into $TARGET ..."
  git clone https://github.com/pallets/flask.git "$TARGET"
  git -C "$TARGET" checkout --quiet "$PINNED_COMMIT"
fi

echo "Installing Flask from the clone (editable) so its tests can run..."
python -m pip install --quiet -e "$TARGET"

cd "$ROOT/scripts"
python 01_repo_stats.py "$TARGET"
python 02_complexity.py "$TARGET"
python 03_hotspots.py "$TARGET"
python 04_changelog_defects.py "$TARGET"
python 05_process.py "$TARGET"
bash 06_coverage.sh "$TARGET" > /dev/null
python 07_diagrams.py "$TARGET"
python 08_charts.py
python 09_verify_open_resource.py
echo
echo "Done. Results are in results/ and charts in results/charts/."
