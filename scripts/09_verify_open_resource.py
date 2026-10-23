"""Step 9: verify a finding from the audit - open_resource default encoding.

CHANGES.rst (3.1.0) says Flask.open_resource, Flask.open_instance_resource and
Blueprint.open_resource take an `encoding` parameter that "defaults to utf-8".
The code is duplicated between flask/app.py and flask/blueprints.py, and the
copies disagree. This script checks:

  1. the declared default of each method (inspect.signature)
  2. whether text-mode opening with the default falls back to the platform
     locale encoding (PEP 597: Python emits EncodingWarning when open() gets
     encoding=None, if run with -X warn_default_encoding)

It must be run with the Flask clone installed (pip install -e target).
Output: results/open_resource_check.json
"""

import inspect
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from common import save_json

PROBE = textwrap.dedent(
    """
    import sys, warnings
    from pathlib import Path
    from flask import Flask, Blueprint

    root = Path(sys.argv[1])
    app = Flask("probe", root_path=str(root), instance_path=str(root / "instance"))
    bp = Blueprint("bp", "probe", root_path=str(root))

    calls = {
        "Flask.open_resource": lambda: app.open_resource("data.txt", "r"),
        "Flask.open_instance_resource": lambda: app.open_instance_resource("data.txt", "r"),
        "Blueprint.open_resource": lambda: bp.open_resource("data.txt", "r"),
    }
    for name, call in calls.items():
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with call() as f:
                enc = f.encoding
        warned = any(w.category.__name__ == "EncodingWarning" for w in caught)
        print(f"{name}|{enc}|{warned}")
    """
)


def main():
    from flask import Blueprint, Flask

    print("Checking open_resource default encoding...")
    declared = {
        "Flask.open_resource": inspect.signature(Flask.open_resource).parameters["encoding"].default,
        "Flask.open_instance_resource": inspect.signature(Flask.open_instance_resource).parameters["encoding"].default,
        "Blueprint.open_resource": inspect.signature(Blueprint.open_resource).parameters["encoding"].default,
    }

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "instance").mkdir()
        for p in (root / "data.txt", root / "instance" / "data.txt"):
            p.write_text("café", encoding="utf-8")
        out = subprocess.run(
            [sys.executable, "-X", "warn_default_encoding", "-c", PROBE, str(root)],
            capture_output=True, text=True, check=True,
        )

    runtime = {}
    for line in out.stdout.strip().splitlines():
        name, enc, warned = line.split("|")
        runtime[name] = {"file_encoding_used": enc, "fell_back_to_locale": warned == "True"}

    result = {
        "documented_default": "utf-8 (CHANGES.rst, version 3.1.0, issue 5504)",
        "declared_default": declared,
        "runtime": runtime,
        "matches_documentation": {k: v == "utf-8" for k, v in declared.items()},
    }
    for name in declared:
        status = "OK" if result["matches_documentation"][name] else "MISMATCH"
        print(f"  {name:32s} default={declared[name]!r:9s} -> {status}")
    save_json("open_resource_check.json", result)


if __name__ == "__main__":
    main()
