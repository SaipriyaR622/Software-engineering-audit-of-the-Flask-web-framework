"""Step 2: code complexity metrics.

Uses radon to compute, for every function in src/flask:
  - cyclomatic complexity (CC) and its A-F rank
and for every module:
  - maintainability index (MI)
Output: results/complexity_functions.csv, results/complexity_modules.csv,
        results/complexity_summary.json
"""

import json
import subprocess
from collections import Counter

import pandas as pd

from common import RESULTS, save_json, target_dir


def radon(*args):
    out = subprocess.run(["radon", *args], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def main():
    repo = target_dir()
    src = repo / "src/flask"
    print("Computing complexity metrics...")

    # Cyclomatic complexity per function/method
    rows = []
    for path, blocks in radon("cc", "-j", "-s", str(src)).items():
        rel = str((repo / path).resolve().relative_to(repo / "src"))
        for b in blocks:
            if b["type"] == "class":
                continue
            name = f'{b["classname"]}.{b["name"]}' if b.get("classname") else b["name"]
            rows.append({"file": rel, "function": name, "line": b["lineno"], "cc": b["complexity"], "rank": b["rank"]})
    funcs = pd.DataFrame(rows).sort_values("cc", ascending=False)
    RESULTS.mkdir(exist_ok=True)
    funcs.to_csv(RESULTS / "complexity_functions.csv", index=False)

    # Maintainability index per module
    mi = radon("mi", "-j", "-s", str(src))
    mods = pd.DataFrame(
        [{"file": str((repo / p).resolve().relative_to(repo / "src")), "mi": round(v["mi"], 1), "mi_rank": v["rank"]} for p, v in mi.items()]
    )
    per_file = funcs.groupby("file").agg(functions=("cc", "size"), total_cc=("cc", "sum"), max_cc=("cc", "max"), mean_cc=("cc", "mean"))
    mods = mods.merge(per_file.reset_index(), on="file", how="left").fillna(0).sort_values("total_cc", ascending=False)
    mods["mean_cc"] = mods["mean_cc"].round(2)
    mods.to_csv(RESULTS / "complexity_modules.csv", index=False)

    ranks = Counter(funcs["rank"])
    summary = {
        "functions_analysed": len(funcs),
        "mean_cc": round(funcs["cc"].mean(), 2),
        "median_cc": float(funcs["cc"].median()),
        "rank_counts": {r: ranks.get(r, 0) for r in "ABCDEF"},
        "pct_rank_A": round(ranks.get("A", 0) / len(funcs) * 100, 1),
        "functions_cc_over_10": int((funcs["cc"] > 10).sum()),
        "top10_functions": funcs.head(10).to_dict("records"),
        "lowest_mi_modules": mods.sort_values("mi").head(5)[["file", "mi", "mi_rank"]].to_dict("records"),
    }
    save_json("complexity_summary.json", summary)


if __name__ == "__main__":
    main()
