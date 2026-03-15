"""Guardrail tests preventing DB runtime ownership in reusable modules."""
from pathlib import Path


FORBIDDEN_PATTERNS = (
    "create_engine(",
    "sessionmaker(",
    "declarative_base(",
)


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
