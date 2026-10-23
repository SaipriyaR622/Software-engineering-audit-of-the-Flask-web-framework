"""Shared helpers for the Flask SE audit scripts."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
CHARTS = RESULTS / "charts"


def target_dir() -> Path:
    """Path to the cloned repository under study (default: ./target)."""
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "target"
    if not (path / ".git").exists():
        sys.exit(f"Not a git repository: {path}\nClone it first: git clone https://github.com/pallets/flask.git target")
    return path.resolve()


def git(repo: Path, *args: str) -> str:
    """Run a git command inside the target repo and return stdout."""
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)
    return out.stdout


def save_json(name: str, data) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / name
    path.write_text(json.dumps(data, indent=2, default=str))
    print(f"  wrote {path.relative_to(ROOT)}")
    return path


def load_json(name: str):
    return json.loads((RESULTS / name).read_text())


def window_start(repo: Path, years: int) -> str:
    """Date `years` before the analysed commit, so results do not drift with today's date."""
    from datetime import date

    head = date.fromisoformat(git(repo, "log", "-1", "--format=%ad", "--date=short").strip())
    return head.replace(year=head.year - years).isoformat()
