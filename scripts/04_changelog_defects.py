"""Step 4: defect and change analysis from CHANGES.rst.

Flask records every user-visible change in CHANGES.rst, grouped by release.
Method:
  1. Parse every bullet from version 2.0.0 onward.
  2. Classify it with transparent keyword rules (first match wins).
  3. Apply manual corrections from data/manual_overrides.csv, where the
     wording alone was not enough to judge (each row has a reason).
  4. Tag every defect with the subsystem it affects.

Output: results/changelog_entries.csv, results/changelog_summary.json
"""

import re
from datetime import date

import pandas as pd

from common import ROOT, RESULTS, save_json, target_dir

# Releases from 2.0.0 (May 2021) onward = the "modern" Flask era.
MIN_VERSION = (2, 0, 0)

DEFECT_TYPES = ("Functional defect", "Type-hint defect", "Regression/Revert", "Security")

# Order matters: the first matching rule wins.
TYPE_RULES = [
    ("Security", r":ghsa:|security|vulnerab"),
    ("Regression/Revert", r"\brevert|re-add|\brestore|accidentally|regression"),
    ("Type-hint defect", r"type hint|typing|type annotation|annotation|\btype for\b|type findings|type check|\bmypy\b|pyright"),
    ("Deprecation/Removal", r"deprecat|\bremove[sd]?\b|\bdrop(ped)? support"),
    ("Compatibility/Dependency", r"python 3\.\d+|minimum (dependency|version|required)|werkzeug >=|requires? (werkzeug|click|jinja)|dependenc|compatib|fips|build backend"),
    ("Functional defect", r"\bfix|\bbug\b|incorrect|correctly|does not fail|no longer (fail|raise|crash|break|error|hide)|fails? (when|if|to)|\bwrong\b|properly|is correct|was not|were not|not being|broken|clearer error|in either order"),
    ("Docs", r"\bdocs?\b|documentation"),
]

AREA_RULES = [
    ("CLI", r"\bcli\b|flask run|flask --|command|click|dotenv|(?<!app)\.env\b|load_dotenv|create_app|flask_app"),
    ("Sessions/Cookies", r"session|cookie|secret_key|samesite|httponly"),
    ("Test client", r"test client|flaskclient|follow_redirects|cli_runner"),
    ("Async", r"\basync|await|asynciterable|coroutine"),
    ("Routing/Blueprints", r"blueprint|url_for|route|url rule|url prefix|url_prefix|endpoint|subdomain|redirect"),
    ("Context/Globals", r"context|\bg\b|current_app|teardown|before_request|after_request|lock"),
    ("Templating", r"template|jinja|render|autoescape"),
    ("JSON", r"json|decimal"),
    ("Static/Files", r"send_file|send_from_directory|static|open_resource|instance_path"),
    ("Config", r"\bconfig\b|from_file|from_prefixed_env|app\.env"),
]


def parse_version(text):
    return tuple(int(x) for x in text.split("."))


def classify(text, rules, default):
    lower = text.lower()
    for label, pattern in rules:
        if re.search(pattern, lower):
            return label
    return default


def parse_changelog(path):
    """Return (version, release_date, entry_text) for every bullet."""
    version, released = None, None
    entry, entries = [], []

    def flush():
        if entry and version:
            entries.append((version, released, " ".join(s.strip() for s in entry)))
        entry.clear()

    for line in path.read_text().splitlines():
        m = re.match(r"^Version (\d+\.\d+\.\d+)", line)
        if m:
            flush()
            version, released = m.group(1), None
            continue
        m = re.match(r"^(Released|Unreleased)(?: on)?\s*(\d{4}-\d{2}-\d{2})?", line)
        if m and version and released is None:
            released = m.group(2) or "unreleased"
            continue
        if line.startswith("-   "):
            flush()
            entry.append(line[4:])
        elif line.startswith("    ") and entry:
            entry.append(line)
        elif not line.strip():
            continue
        else:
            flush()
    flush()
    return entries


def apply_overrides(df):
    """Apply manual corrections; return the updated frame and how many changed."""
    overrides = pd.read_csv(ROOT / "data/manual_overrides.csv")
    df["rule_type"] = df["type"]
    df["override_reason"] = ""
    df["area_override"] = ""
    unmatched = []
    for _, o in overrides.iterrows():
        mask = (df["version"] == o["version"]) & df["text"].str.startswith(o["text_starts_with"])
        if mask.sum() != 1:
            unmatched.append(f'{o["version"]}: {o["text_starts_with"]}')
            continue
        if isinstance(o["type"], str) and o["type"]:
            df.loc[mask, "type"] = o["type"]
        if isinstance(o["area"], str) and o["area"]:
            df.loc[mask, "area_override"] = o["area"]
        df.loc[mask, "override_reason"] = o["reason"]
    if unmatched:
        print("  WARNING: overrides that matched no single entry:", *unmatched, sep="\n    ")
    changed = int((df["type"] != df["rule_type"]).sum())
    return df, changed


def main():
    repo = target_dir()
    print("Classifying CHANGES.rst entries...")
    rows = []
    for version, released, text in parse_changelog(repo / "CHANGES.rst"):
        if parse_version(version) < MIN_VERSION:
            continue
        major, minor, patch = parse_version(version)
        rows.append(
            {
                "version": version,
                "line": f"{major}.{minor}",
                "released": released,
                "release_kind": "patch" if patch else "feature",
                "type": classify(text, TYPE_RULES, "Feature/Enhancement"),
                "refs": ";".join(re.findall(r":(?:issue|pr|ghsa):`([^`]+)`", text)),
                "text": re.sub(r"\s+", " ", text)[:300],
            }
        )

    df = pd.DataFrame(rows)
    df, changed = apply_overrides(df)
    df["is_defect"] = df["type"].isin(DEFECT_TYPES)
    df["area"] = [
        (ov or classify(t, AREA_RULES, "Other/Core")) if d else ""
        for t, d, ov in zip(df["text"], df["is_defect"], df["area_override"])
    ]
    df = df.drop(columns="area_override")
    df.to_csv(RESULTS / "changelog_entries.csv", index=False)

    defects = df[df["is_defect"]]
    released = df[df["released"] != "unreleased"]
    releases = released[["version", "released", "release_kind"]].drop_duplicates().sort_values(["released", "version"])
    gaps = pd.to_datetime(releases["released"]).diff().dt.days.dropna()

    # Defects fixed in patch releases escaped the feature release of that line.
    escaped = (
        defects[defects["release_kind"] == "patch"].groupby("line").size().reindex(sorted(df["line"].unique(), key=parse_version), fill_value=0)
    )

    save_json(
        "changelog_summary.json",
        {
            "from_version": ".".join(map(str, MIN_VERSION)),
            "entries": len(df),
            "entries_released": len(released),
            "rule_entries_corrected_manually": changed,
            "rule_accuracy_pct": round((1 - changed / len(df)) * 100, 1),
            "releases": int(releases["version"].nunique()),
            "feature_releases": int((releases["release_kind"] == "feature").sum()),
            "patch_releases": int((releases["release_kind"] == "patch").sum()),
            "median_days_between_releases": float(gaps.median()),
            "by_type": df["type"].value_counts().to_dict(),
            "defects_total": len(defects),
            "defects_pct_of_entries": round(len(defects) / len(df) * 100, 1),
            "defects_in_patch_releases": int((defects["release_kind"] == "patch").sum()),
            "pct_defects_in_patch": round((defects["release_kind"] == "patch").mean() * 100, 1),
            "defects_by_type": defects["type"].value_counts().to_dict(),
            "defects_by_area": defects["area"].value_counts().to_dict(),
            "area_by_type": pd.crosstab(defects["area"], defects["type"]).to_dict("index"),
            "escaped_defects_per_line": escaped.to_dict(),
            "patch_releases_per_line": releases[releases["release_kind"] == "patch"]
            .assign(line=lambda r: r["version"].str.rsplit(".", n=1).str[0])
            .groupby("line")
            .size()
            .to_dict(),
            "release_dates": dict(zip(releases["version"], releases["released"])),
            "generated": str(date.today()),
        },
    )


if __name__ == "__main__":
    main()
