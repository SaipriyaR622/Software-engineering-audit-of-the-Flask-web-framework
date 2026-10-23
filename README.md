# Software Engineering Audit of Flask

Scripts used to study the open-source web framework [Flask](https://github.com/pallets/flask)
as a software engineering case study: size and history, code complexity, change hotspots,
test coverage, design recovery (class and module diagrams), development process, and
defect analysis from the project's changelog.

All numbers in the report come from these scripts run against Flask commit
`d086db85` (7 October 2026, after release 3.1.3).

## Project structure

```
flask-se-audit/
├── run_all.sh                    # runs every step in order
├── requirements.txt
├── data/
│   └── manual_overrides.csv      # manual corrections to the changelog classification
├── scripts/
│   ├── common.py                 # shared helpers (paths, git, JSON)
│   ├── 01_repo_stats.py          # LOC, commits, contributors, commits per year
│   ├── 02_complexity.py          # cyclomatic complexity + maintainability index (radon)
│   ├── 03_hotspots.py            # churn (git history) x complexity
│   ├── 04_changelog_defects.py   # classify CHANGES.rst entries, defect analysis
│   ├── 05_process.py             # CI workflows, pre-commit hooks, PR / branch merges
│   ├── 06_coverage.sh            # run Flask's test suite with coverage
│   ├── 07_diagrams.py            # class hierarchy + module dependency graph (ast + Graphviz)
│   ├── 07_uml_pyreverse.sh       # optional: pyreverse UML (for comparison)
│   ├── 08_charts.py              # charts for the report
│   └── 09_verify_open_resource.py # checks the open_resource encoding finding
└── results/                      # generated: CSV / JSON outputs and charts/
```

## Requirements

- Python 3.11 or newer
- Git
- Graphviz (`dot` command) for the diagrams
  - Ubuntu/Debian: `sudo apt install graphviz`
  - macOS: `brew install graphviz`
  - Windows: install from graphviz.org and add it to PATH

No API keys or environment variables are needed. Everything runs offline after the clone.

## Setup

```bash
git clone <this-repo-url> flask-se-audit
cd flask-se-audit

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Running

Run everything (clones Flask into `target/` at the pinned commit if it is not there):

```bash
./run_all.sh
```

On Windows, run the steps from Git Bash, or run each script by hand:

```bash
git clone https://github.com/pallets/flask.git target
git -C target checkout d086db856be187255b8ec61ef409357393020f32
pip install -e target
cd scripts
python 01_repo_stats.py
python 02_complexity.py
python 03_hotspots.py
python 04_changelog_defects.py
python 05_process.py
bash 06_coverage.sh
python 07_diagrams.py
python 08_charts.py
python 09_verify_open_resource.py
```

Each script takes an optional path to the Flask clone (default `../target`).
Steps 3 and 8 read outputs of earlier steps, so keep the order.

## Outputs

| File | Contents |
|---|---|
| `results/repo_stats.json` | commits, contributors, commits per year, lines of code |
| `results/complexity_functions.csv` | cyclomatic complexity of every function |
| `results/complexity_modules.csv` | maintainability index and complexity per module |
| `results/hotspots.csv` | churn, complexity and hotspot score per module |
| `results/changelog_entries.csv` | every changelog entry since 2.0.0 with its type and area |
| `results/changelog_summary.json` | defect counts by type, area and release line |
| `results/process_summary.json` | CI jobs, hooks, tools, merge counts |
| `results/coverage.json` | per-file coverage from Flask's own test suite |
| `results/design_summary.json` | classes, import kinds, import cycles, fan-in / fan-out |
| `results/open_resource_check.json` | declared vs. documented default encoding of `open_resource` |
| `results/charts/*.png` | all figures used in the report |

## Method notes

- **Complexity**: radon cyclomatic complexity (rank A = 1-5 ... F = 41+) and maintainability index.
- **Hotspots**: commits touching each file in the last 5 years (renames followed) multiplied by the
  file's total complexity, both scaled to 0-1.
- **Defects**: Flask has no "bug" label history available offline, so the changelog is used.
  Each entry since 2.0.0 is classified by keyword rules, then reviewed by hand;
  29 of 181 rule labels were corrected and every correction is listed with a reason in
  `data/manual_overrides.csv`.
- **Imports**: imports are split into runtime, lazy (inside a function) and
  type-checking-only, so import cycles are reported for each case.

## Limitations

- Changelog entries record user-visible changes only. Internal fixes that never reached the
  changelog are not counted.
- Keyword classification depends on wording; the manual review reduces but does not remove
  this bias.
- Coverage is measured on one platform (Linux, Python 3.13), while Flask's CI runs 11 configurations.
