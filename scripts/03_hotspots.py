"""Step 3: hotspot analysis (churn x complexity).

Churn = how often a file changed. Files that change often AND are complex are
where defects are most likely (Tornhill, "Your Code as a Crime Scene").

Churn is measured over the last WINDOW_YEARS years with `git log --numstat`.
Renames are followed so the 2023 move into src/flask/sansio/ is not lost.
Output: results/hotspots.csv, results/hotspots_summary.json
"""

import re
from collections import defaultdict

import pandas as pd

from common import RESULTS, git, save_json, target_dir, window_start

WINDOW_YEARS = 5


def normalise(path):
    """Resolve git rename notation like src/flask/{app.py => sansio/app.py}."""
    m = re.match(r"(.*)\{(.*) => (.*)\}(.*)", path)
    if m:
        path = m.group(1) + m.group(3) + m.group(4)
    elif " => " in path:
        path = path.split(" => ")[1]
    return path.replace("//", "/")


def main():
    repo = target_dir()
    since = window_start(repo, WINDOW_YEARS)
    print(f"Mining git history since {since} ({WINDOW_YEARS} years before the analysed commit)...")
    log = git(repo, "log", f"--since={since}", "--no-merges", "-M", "--numstat", "--format=@@%H|%ad", "--date=short")

    commits, lines_changed = defaultdict(set), defaultdict(int)
    current = None
    for line in log.splitlines():
        if line.startswith("@@"):
            current = line[2:].split("|")[0]
            continue
        parts = line.split("\t")
        if len(parts) != 3 or current is None:
            continue
        added, deleted, path = parts
        path = normalise(path)
        if not (path.startswith("src/flask/") and path.endswith(".py")):
            continue
        commits[path].add(current)
        if added != "-":
            lines_changed[path] += int(added) + int(deleted)

    churn = pd.DataFrame(
        [{"file": p.removeprefix("src/"), "commits": len(c), "lines_changed": lines_changed[p]} for p, c in commits.items()]
    )
    mods = pd.read_csv(RESULTS / "complexity_modules.csv")
    df = mods.merge(churn, on="file", how="left").fillna({"commits": 0, "lines_changed": 0})

    # Normalise both axes to 0-1 and multiply: high only when both are high.
    df["churn_norm"] = df["commits"] / df["commits"].max()
    df["cc_norm"] = df["total_cc"] / df["total_cc"].max()
    df["hotspot_score"] = (df["churn_norm"] * df["cc_norm"]).round(3)
    df = df.sort_values("hotspot_score", ascending=False)
    df.to_csv(RESULTS / "hotspots.csv", index=False)

    save_json(
        "hotspots_summary.json",
        {
            "window_years": WINDOW_YEARS,
            "since": since,
            "files": len(df),
            "top5": df.head(5)[["file", "commits", "lines_changed", "total_cc", "max_cc", "mi", "hotspot_score"]].to_dict("records"),
        },
    )


if __name__ == "__main__":
    main()
