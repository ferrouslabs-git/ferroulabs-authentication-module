"""Fix misplaced async_test_utils imports in test files.

The bulk conversion script inserted `from tests.async_test_utils import make_test_db, make_async_app`
in the wrong location (middle of functions). This script:
1. Removes the misplaced import line
2. Adds it to the top-level imports
"""
import re
from pathlib import Path

IMPORT_LINE = "from tests.async_test_utils import make_test_db, make_async_app"

files_to_fix = [
    "test_cognito_admin_ops.py",
    "test_cognito_integration.py",
    "test_config_routes_api.py",
    "test_cookie_token_endpoints.py",
    "test_cross_feature_integration.py",
    "test_e2e_auth_lifecycle.py",
    "test_platform_tenant_api.py",
    "test_rate_limiter_service.py",
    "test_route_integration.py",
    "test_space_routes_api.py",
]

tests_dir = Path(__file__).parent

for fname in files_to_fix:
    fpath = tests_dir / fname
    if not fpath.exists():
        print(f"SKIP {fname}: not found")
        continue

    lines = fpath.read_text(encoding="utf-8").splitlines(keepends=True)

    # Find and remove the misplaced import line
    new_lines = []
    removed = False
    for line in lines:
        stripped = line.strip()
        if stripped == IMPORT_LINE and not removed:
            removed = True
            continue
        new_lines.append(line)

    if not removed:
        print(f"SKIP {fname}: import line not found in body")
        continue

    # Check if import already exists at top level
    has_top_import = any(
        l.strip() == IMPORT_LINE
        for l in new_lines[:50]
    )

    if not has_top_import:
        # Find the last top-level import/from line to insert after
        insert_idx = 0
        for i, line in enumerate(new_lines):
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                # Check it's top-level (no leading whitespace)
                if line[0] not in (" ", "\t"):
                    insert_idx = i + 1

        new_lines.insert(insert_idx, IMPORT_LINE + "\n")

    fpath.write_text("".join(new_lines), encoding="utf-8")
    print(f"FIXED {fname}: moved import to top (line {insert_idx + 1})")

print("\nDone!")
