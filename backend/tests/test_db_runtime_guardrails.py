"""Guardrail tests preventing DB runtime ownership in reusable modules."""
import glob
import re
from pathlib import Path

import pytest


FORBIDDEN_PATTERNS = (
    "create_engine(",
    "sessionmaker(",
    "declarative_base(",
)


def test_no_require_role_in_route_files():
    """require_role() is deprecated. Route files must use require_permission()."""
    api_dir = Path(__file__).resolve().parents[1] / "app" / "auth_usermanagement" / "api"
    pattern = re.compile(r"\brequire_role\s*\(")
    violations = []
    for py_file in api_dir.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        source = py_file.read_text(encoding="utf-8")
        for i, line in enumerate(source.splitlines(), 1):
            if pattern.search(line):
                rel = py_file.relative_to(Path(__file__).resolve().parents[1])
                violations.append(f"{rel}:{i}")
    assert not violations, f"require_role() found in route files (use require_permission): {violations}"


def test_reusable_module_does_not_create_db_runtime_objects():
    module_root = Path(__file__).resolve().parents[1] / "app" / "auth_usermanagement"

    violations: list[str] = []
    for py_file in module_root.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue

        source = py_file.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in source:
                rel = py_file.relative_to(Path(__file__).resolve().parents[1])
                violations.append(f"{rel}: contains forbidden pattern '{pattern}'")

    assert not violations, "\n".join(violations)
