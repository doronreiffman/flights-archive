"""The frozen rule's modules import no other part of the site, so that `git diff <tag> -- <frozen files>` shows every
change to the rule (docs/flight-lookup-plan.md, "Frozen files"; docs/flight-lookup.md, "The record", condition 1)."""
import ast
import sys
from pathlib import Path

import pytest

TIMELINE = Path(__file__).resolve().parent.parent / "src" / "timeline"
FROZEN = {"load", "counting"}  # Tasks 2 and 6 add "rates" and "record"
ALLOWED = {"model", "duckdb"}  # beside the standard library


def foreign_imports(source: str) -> list[str]:
    """Each import in `source` that names a timeline module outside FROZEN, or a package that is neither the
    standard library, `model` nor `duckdb`."""
    def outside(top: str) -> bool:
        return top not in ALLOWED and top not in sys.stdlib_module_names

    bad = []
    for node in ast.walk(ast.parse(source)):
        line = ast.unparse(node) if isinstance(node, (ast.Import, ast.ImportFrom)) else ""
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if (parts[0] == "timeline" and (len(parts) < 2 or parts[1] not in FROZEN)) or (
                        parts[0] != "timeline" and outside(parts[0])):
                    bad.append(line)
        elif isinstance(node, ast.ImportFrom):
            parts = node.module.split(".") if node.module else []
            if node.level > 1:  # above the timeline package
                bad.append(line)
            elif node.level == 1 or parts[0] == "timeline":
                named = parts[node.level == 0:]  # the timeline module in `from .x` or `from timeline.x`
                modules = named[:1] or [alias.name for alias in node.names]
                if any(m not in FROZEN for m in modules):
                    bad.append(line)
            elif outside(parts[0]):
                bad.append(line)
    return bad


def test_frozen_modules_import_only_frozen_modules():
    found = {name: foreign_imports((TIMELINE / f"{name}.py").read_text(encoding="utf-8")) for name in sorted(FROZEN)}
    assert found == {name: [] for name in sorted(FROZEN)}


@pytest.mark.parametrize("source", [
    "from . import words", "from .words import ISRAEL", "from . import counting, views", "from timeline import flights",
    "from timeline.views import front_page", "import timeline.check", "import timeline", "from .. import collector",
    "def f():\n    from . import words", "import requests", "from collector import core",
])
def test_the_guard_refuses_an_import_from_outside_the_frozen_rule(source):
    assert foreign_imports(source) != []


@pytest.mark.parametrize("source", [
    "from __future__ import annotations", "from . import counting", "from .load import load", "from . import load, counting",
    "from timeline import counting", "from timeline.load import OBS_COLUMNS", "import timeline.counting",
    "from model.rules import GAP_HOURS", "import duckdb", "from datetime import datetime, timedelta", "import bisect",
])
def test_the_guard_allows_the_frozen_rule_the_model_duckdb_and_the_standard_library(source):
    assert foreign_imports(source) == []
