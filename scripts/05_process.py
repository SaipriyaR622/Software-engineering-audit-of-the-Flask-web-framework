"""Step 5: development process evidence.

Reads the repository's CI workflows, pre-commit hooks and tooling config, and
measures how much work arrives via merged pull requests.
Output: results/process_summary.json
"""

import re
import tomllib

from common import git, save_json, target_dir, window_start


def main():
    repo = target_dir()
    print("Collecting process evidence...")

    workflows = {}
    for wf in sorted((repo / ".github/workflows").glob("*.y*ml")):
        text = wf.read_text()
        triggers = re.findall(r"^\s{2}(push|pull_request|schedule|workflow_dispatch|release|issues)\s*:", text, re.M)
        workflows[wf.name] = {
            "name": (re.search(r"^name:\s*(.+)$", text, re.M) or [None, wf.stem])[1],
            "triggers": sorted(set(triggers)),
            "python_versions": sorted(set(re.findall(r"python:\s*'?([0-9.t]+|pypy[0-9.]+)'?", text))),
            "os": sorted(set(re.findall(r"os:\s*([a-z]+-[a-z0-9.]+)", text))),
        }

    hooks = re.findall(r"^\s*-\s*id:\s*(\S+)", (repo / ".pre-commit-config.yaml").read_text(), re.M)
    pyproject = tomllib.loads((repo / "pyproject.toml").read_text())
    tool = pyproject.get("tool", {})

    since = window_start(repo, 5)
    merges = git(repo, "log", "--merges", f"--since={since}", "--format=%s").splitlines()
    pr_merges = [m for m in merges if re.search(r"Merge pull request #\d+", m)]
    branch_merges = [m for m in merges if re.search(r"Merge branch '(stable|\d+\.\d+\.x)'", m)]
    all_commits = int(git(repo, "rev-list", "--count", "--no-merges", f"--since={since}", "HEAD"))

    save_json(
        "process_summary.json",
        {
            "window_since": since,
            "workflows": workflows,
            "pre_commit_hooks": hooks,
            "configured_tools": sorted(tool.keys()),
            "mypy_strict": bool(tool.get("mypy", {}).get("strict")),
            "dependencies": pyproject["project"].get("dependencies", []),
            "requires_python": pyproject["project"].get("requires-python"),
            "last5y_non_merge_commits": all_commits,
            "last5y_pr_merges": len(pr_merges),
            "last5y_stable_branch_merges": len(branch_merges),
            "has_contributing": any((repo / p).exists() for p in ["CONTRIBUTING.rst", "CONTRIBUTING.md", ".github/CONTRIBUTING.md", "docs/contributing.rst"]),
            "issue_templates": sorted(p.name for p in (repo / ".github/ISSUE_TEMPLATE").glob("*")) if (repo / ".github/ISSUE_TEMPLATE").exists() else [],
            "has_pr_template": (repo / ".github/pull_request_template.md").exists(),
        },
    )


if __name__ == "__main__":
    main()
