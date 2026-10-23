"""Step 1: basic repository statistics.

Collects size (lines of code), commit history, contributors, commits per year
and the module list of the main package.
Output: results/repo_stats.json
"""

import subprocess
from collections import Counter

from common import git, save_json, target_dir


def count_lines(repo, folder):
    """Count code / comment / blank lines of Python files with radon raw metrics."""
    out = subprocess.run(["radon", "raw", "-s", "-j", str(repo / folder)], capture_output=True, text=True, check=True)
    import json

    data = json.loads(out.stdout)
    totals = Counter()
    for metrics in data.values():
        if "error" in metrics:
            continue
        for key in ("loc", "sloc", "comments", "multi", "blank"):
            totals[key] += metrics[key]
    totals["files"] = len(data)
    return dict(totals)


def main():
    repo = target_dir()
    print("Collecting repository statistics...")

    commits = git(repo, "log", "--format=%H|%an|%ad", "--date=short").strip().splitlines()
    authors = Counter(line.split("|")[1] for line in commits)
    years = Counter(line.split("|")[2][:4] for line in commits)

    top_share = sum(c for _, c in authors.most_common(5)) / len(commits)

    stats = {
        "head_commit": git(repo, "rev-parse", "--short", "HEAD").strip(),
        "head_date": git(repo, "log", "-1", "--format=%ad", "--date=short").strip(),
        "first_commit_date": commits[-1].split("|")[2],
        "latest_tag": git(repo, "describe", "--tags", "--abbrev=0").strip(),
        "total_commits": len(commits),
        "contributors": len(authors),
        "top5_authors": authors.most_common(5),
        "top5_commit_share": round(top_share * 100, 1),
        "commits_per_year": dict(sorted(years.items())),
        "loc_src": count_lines(repo, "src/flask"),
        "loc_tests": count_lines(repo, "tests"),
        "modules": sorted(p.relative_to(repo / "src").as_posix() for p in (repo / "src/flask").rglob("*.py")),
    }
    save_json("repo_stats.json", stats)


if __name__ == "__main__":
    main()
