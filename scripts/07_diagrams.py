"""Step 7: design recovery diagrams generated from the source code.

Parses every module in src/flask with Python's ast module and produces:
  1. class_hierarchy.png     - inheritance between Flask's core classes
                               (plus the external base classes they extend)
  2. module_dependencies.png - which internal module imports which
       solid  = import at module load time (runtime)
       dashed = import inside a function (lazy, runs only when called)
       imports under `if TYPE_CHECKING:` are left out (never run)
Also writes results/design_summary.json: classes, import counts by kind,
fan-in / fan-out per module, and import cycles for each graph.

pyreverse (07_uml_pyreverse.sh) can be used too, but it does not resolve the
sansio base classes, so the key Flask -> App -> Scaffold chain is missing.
Requires Graphviz (`dot`) on PATH.
"""

import ast
import subprocess
from collections import defaultdict

from common import CHARTS, save_json, target_dir

CORE_CLASSES = {
    "Scaffold", "App", "Flask", "Blueprint", "SessionInterface",
    "SecureCookieSessionInterface", "SecureCookieSession", "NullSession", "SessionMixin",
    "Request", "Response", "FlaskClient", "View", "MethodView", "Config",
    "JSONProvider", "DefaultJSONProvider", "FlaskGroup", "AppGroup",
}
IGNORED_BASES = {"object", "t.Generic", "Generic", "Protocol", "t.Protocol"}


def module_name(src, path):
    parts = path.relative_to(src).with_suffix("").parts
    return ".".join(p for p in parts if p != "__init__")


def import_targets(mod, is_pkg, node):
    """Internal module names an ImportFrom node refers to ('' = the flask package)."""
    if node.level == 0:
        if not (node.module and (node.module == "flask" or node.module.startswith("flask."))):
            return []
        base = node.module.removeprefix("flask").strip(".")
    else:
        package = mod.split(".") if mod else []
        if not is_pkg:
            package = package[:-1]
        if node.level > 1:
            package = package[: len(package) - (node.level - 1)]
        base = ".".join(package + ([node.module] if node.module else []))
    if node.module is None or base == "":
        # "from . import x" / "from flask import x" may import submodules
        return [f"{base}.{a.name}".strip(".") for a in node.names] + [base]
    return [base]


def is_type_checking(test):
    return ast.unparse(test) in ("TYPE_CHECKING", "t.TYPE_CHECKING", "typing.TYPE_CHECKING")


def walk_imports(body, kind="runtime"):
    """Yield (ImportFrom node, kind) with kind in runtime / lazy / typing."""
    for node in body:
        if isinstance(node, ast.ImportFrom):
            yield node, kind
        elif isinstance(node, ast.If) and is_type_checking(node.test):
            yield from walk_imports(node.body, "typing")
            yield from walk_imports(node.orelse, kind)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield from walk_imports(node.body, "typing" if kind == "typing" else "lazy")
        elif isinstance(node, ast.ClassDef):
            yield from walk_imports(node.body, kind)
        elif isinstance(node, (ast.If, ast.Try, ast.With, ast.For, ast.While)):
            for field in ("body", "orelse", "finalbody"):
                yield from walk_imports(getattr(node, field, []), kind)
            for handler in getattr(node, "handlers", []):
                yield from walk_imports(handler.body, kind)


def collect(src):
    modules = {module_name(src, p): p for p in src.rglob("*.py")}
    classes = {}
    edges = defaultdict(lambda: defaultdict(set))  # kind -> module -> targets
    for mod, path in modules.items():
        tree = ast.parse(path.read_text())
        is_pkg = path.name == "__init__.py"
        # "from .sansio.blueprints import Blueprint as SansioBlueprint" -> resolve the alias
        aliases = {a.asname: a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names if a.asname}
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = [ast.unparse(b).split("[")[0] for b in node.bases]
                bases = [aliases.get(b, b) for b in bases]
                classes[f"{mod}.{node.name}"] = {"name": node.name, "module": mod, "bases": bases}
        for node, kind in walk_imports(tree.body):
            for t in import_targets(mod, is_pkg, node):
                if t in modules and t != mod and mod != "":
                    edges[kind][mod].add(t)
    # The package __init__ only re-exports; drop it as a target to keep graphs readable.
    for kind in edges:
        for mod in edges[kind]:
            edges[kind][mod].discard("")
    return modules, classes, edges


def find_cycles(graph):
    """Strongly connected components with more than one module (Tarjan's algorithm)."""
    index, low, stack, on, out, counter = {}, {}, [], set(), [], [0]

    def strong(v):
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on.add(v)
        for w in graph.get(v, ()):
            if w not in index:
                strong(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on.discard(w)
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1:
                out.append(sorted(comp))

    for v in list(graph):
        if v not in index:
            strong(v)
    return out


def merge(*graphs):
    out = defaultdict(set)
    for g in graphs:
        for k, v in g.items():
            out[k] |= v
    return out


def render(dot_source, name):
    CHARTS.mkdir(parents=True, exist_ok=True)
    (CHARTS / f"{name}.dot").write_text(dot_source)
    subprocess.run(["dot", "-Tpng", "-Gdpi=170", "-o", str(CHARTS / f"{name}.png")], input=dot_source, text=True, check=True)
    print(f"  wrote results/charts/{name}.png")


def class_diagram(classes):
    by_name = defaultdict(list)
    for key, c in classes.items():
        by_name[c["name"]].append(key)

    lines = [
        "digraph G {", "rankdir=LR; nodesep=0.18; ranksep=0.55;",
        'node [shape=box, fontname="Helvetica", fontsize=10, style=filled, fillcolor="#EEF3F8", color="#4A6582"];',
        'edge [arrowhead=empty, color="#4A6582"];',
    ]
    shown, external = set(), set()
    for key, c in classes.items():
        if c["name"] not in CORE_CLASSES:
            continue
        shown.add(key)
        for b in c["bases"]:
            short = b.split(".")[-1]
            candidates = [k for k in by_name.get(short, []) if k != key]
            if candidates:
                # e.g. flask.app.Flask(App) -> the App defined in sansio.app
                target = next((k for k in candidates if "sansio" in k), candidates[0])
                shown.add(target)
                lines.append(f'"{key}" -> "{target}";')
            elif b not in IGNORED_BASES:
                external.add(b)
                lines.append(f'"{key}" -> "ext:{b}";')
    for key in sorted(shown):
        c = classes[key]
        lines.append(f'"{key}" [label="{c["name"]}\\n({c["module"]})"];')
    for b in sorted(external):
        lines.append(f'"ext:{b}" [label="{b}\\n(external)", fillcolor="#F4F4F4", color="#999999", fontcolor="#555555"];')
    lines.append("}")
    render("\n".join(lines), "class_hierarchy")


def module_diagram(runtime, lazy):
    lines = [
        "digraph G {", "rankdir=LR; nodesep=0.22; ranksep=0.7;",
        'node [shape=box, fontname="Helvetica", fontsize=10, style="filled,rounded", fillcolor="#EEF3F8", color="#4A6582"];',
        'edge [color="#6F8399", arrowsize=0.6];',
    ]
    for a in sorted(runtime):
        for b in sorted(runtime[a]):
            lines.append(f'"{a}" -> "{b}";')
    for a in sorted(lazy):
        for b in sorted(lazy[a] - runtime.get(a, set())):
            lines.append(f'"{a}" -> "{b}" [style=dashed, color="#C0392B"];')
    lines.append("}")
    render("\n".join(lines), "module_dependencies")


def count(graph):
    return sum(len(v) for v in graph.values())


def main():
    repo = target_dir()
    src = repo / "src/flask"
    print("Recovering design from source...")
    modules, classes, edges = collect(src)
    runtime, lazy, typing_only = edges["runtime"], edges["lazy"], edges["typing"]

    fan_in = defaultdict(int)
    for targets in runtime.values():
        for t in targets:
            fan_in[t] += 1
    coupling = sorted(
        ({"module": m, "fan_out": len(runtime.get(m, ())), "fan_in": fan_in.get(m, 0)} for m in modules if m),
        key=lambda r: (r["fan_in"] + r["fan_out"]),
        reverse=True,
    )

    class_diagram(classes)
    module_diagram(runtime, lazy)
    save_json(
        "design_summary.json",
        {
            "modules": len(modules),
            "classes": len(classes),
            "import_edges": {"runtime": count(runtime), "lazy": count(lazy), "typing_only": count(typing_only)},
            "cycles_runtime_only": find_cycles(runtime),
            "cycles_if_lazy_were_top_level": find_cycles(merge(runtime, lazy)),
            "cycles_if_all_imports_top_level": find_cycles(merge(runtime, lazy, typing_only)),
            "lazy_imports": {m: sorted(t) for m, t in sorted(lazy.items())},
            "class_bases": {k: v["bases"] for k, v in classes.items() if v["name"] in CORE_CLASSES},
            "coupling": coupling,
        },
    )


if __name__ == "__main__":
    main()
