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


def test_no_direct_host_database_imports_outside_bridge():
    """All auth_usermanagement files must import DB objects through the module's
    own database.py bridge — never directly from 'app.database'.

    The only file allowed to reference 'from app.database' is the bridge file
    auth_usermanagement/database.py itself.
    """
    module_root = Path(__file__).resolve().parents[1] / "app" / "auth_usermanagement"
    bridge_file = module_root / "database.py"
    host_import_pattern = re.compile(r"from\s+app\.database\s+import")

    violations: list[str] = []
    for py_file in module_root.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        if py_file.resolve() == bridge_file.resolve():
            continue

        source = py_file.read_text(encoding="utf-8")
        for i, line in enumerate(source.splitlines(), 1):
            if host_import_pattern.search(line):
                rel = py_file.relative_to(Path(__file__).resolve().parents[1])
                violations.append(f"{rel}:{i}")

    assert not violations, (
        "Direct 'from app.database import ...' found outside bridge file. "
        "Use relative imports (from ..database import ...) instead:\n"
        + "\n".join(violations)
    )
