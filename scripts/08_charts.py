"""Step 8: charts for the report, built from the results/ files.

Run after steps 1-7. All charts are saved as PNG in results/charts/.
Single-hue bars are used for magnitudes; one accent colour highlights the
items discussed in the report.
"""

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from common import CHARTS, RESULTS, load_json

BLUE = "#2a78d6"
ACCENT = "#eb6834"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK_2,
    "xtick.color": INK_2, "ytick.color": INK_2, "axes.titlesize": 11, "axes.titleweight": "bold",
    "axes.titlecolor": INK, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True, "figure.dpi": 160,
})


def save(fig, name):
    CHARTS.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(CHARTS / f"{name}.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  wrote results/charts/{name}.png")


def hbar(series, title, xlabel, name, highlight=(), fmt="{:.0f}", width=6.4):
    series = series.sort_values()
    fig, ax = plt.subplots(figsize=(width, 0.36 * len(series) + 1.0))
    colors = [ACCENT if k in highlight else BLUE for k in series.index]
    bars = ax.barh(series.index, series.values, color=colors, height=0.62)
    ax.bar_label(bars, labels=[fmt.format(v) for v in series.values], padding=3, color=INK_2, fontsize=9)
    ax.set_title(title, loc="left")
    ax.set_xlabel(xlabel)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, series.max() * 1.15)
    save(fig, name)


def main():
    print("Drawing charts...")
    stats = load_json("repo_stats.json")
    cx = load_json("complexity_summary.json")
    cl = load_json("changelog_summary.json")

    # 1. Commit activity per year
    years = pd.Series(stats["commits_per_year"])
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    ax.bar(years.index, years.values, color=BLUE, width=0.7)
    ax.set_title("Commits per year", loc="left")
    ax.set_ylabel("Commits")
    ax.grid(axis="x", visible=False)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    save(fig, "commits_per_year")

    # 2. Cyclomatic complexity rank distribution
    ranks = pd.Series(cx["rank_counts"])
    labels = {"A": "A (1-5)", "B": "B (6-10)", "C": "C (11-20)", "D": "D (21-30)", "E": "E (31-40)", "F": "F (41+)"}
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    bars = ax.bar([labels[r] for r in ranks.index], ranks.values, color=[BLUE if r in "AB" else ACCENT for r in ranks.index], width=0.65)
    ax.bar_label(bars, padding=2, color=INK_2, fontsize=9)
    ax.set_title(f"Functions by cyclomatic complexity rank (n = {cx['functions_analysed']})", loc="left")
    ax.set_ylabel("Functions")
    ax.grid(axis="x", visible=False)
    save(fig, "complexity_ranks")

    # 3. Hotspots: churn vs complexity per module
    hs = pd.read_csv(RESULTS / "hotspots.csv")
    top = set(hs.head(3)["file"])
    fig, ax = plt.subplots(figsize=(7.0, 4.4))
    for is_top in (False, True):
        part = hs[hs["file"].isin(top) == is_top]
        ax.scatter(part["commits"], part["total_cc"], s=46, color=ACCENT if is_top else BLUE,
                   edgecolor="white", linewidth=1.2, zorder=3)
    labelled = set(hs.head(5)["file"]) | {"flask/sansio/blueprints.py"}
    for _, r in hs.iterrows():
        if r["file"] in labelled:
            offset = (6, -12) if r["file"] == "flask/sansio/blueprints.py" else (6, 4)
            ax.annotate(r["file"].removeprefix("flask/"), (r["commits"], r["total_cc"]), xytext=offset,
                        textcoords="offset points", fontsize=8.5, color=INK)
    ax.set_title("Hotspots: change frequency vs. complexity (last 5 years)", loc="left")
    ax.set_xlabel("Commits touching the file")
    ax.set_ylabel("Total cyclomatic complexity")
    save(fig, "hotspots")

    # 4. Coverage per module
    cov = json.loads((RESULTS / "coverage.json").read_text())
    per = pd.Series({
        f.removeprefix("src/flask/"): d["summary"]["percent_covered"]
        for f, d in cov["files"].items() if d["summary"]["num_statements"] > 10
    })
    hbar(per, "Test coverage by module (statements + branches, %)", "Coverage %", "coverage_by_module",
         highlight={k for k, v in per.items() if v < 84}, width=6.6)

    # 5. All changelog entries by type
    hbar(pd.Series(cl["by_type"]), f"Changelog entries by type, 2.0.0 onward (n = {cl['entries']})",
         "Entries", "changes_by_type",
         highlight={"Functional defect", "Type-hint defect", "Regression/Revert", "Security"})

    # 6. Defects by subsystem
    hbar(pd.Series(cl["defects_by_area"]), f"Defects by subsystem (n = {cl['defects_total']})", "Defects",
         "defects_by_area")

    # 7. Defects fixed after each feature release
    esc = pd.Series(cl["escaped_defects_per_line"])
    esc = esc[esc.index != max(esc.index, key=lambda v: tuple(map(int, v.split("."))))]  # drop unreleased line
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    bars = ax.bar([f"{v}.x" for v in esc.index], esc.values, color=[ACCENT if v == esc.max() else BLUE for v in esc.values], width=0.6)
    ax.bar_label(bars, padding=2, color=INK_2, fontsize=9)
    ax.set_title("Defects fixed in patch releases, per release line", loc="left")
    ax.set_ylabel("Defects")
    ax.grid(axis="x", visible=False)
    save(fig, "escaped_defects")


if __name__ == "__main__":
    main()
