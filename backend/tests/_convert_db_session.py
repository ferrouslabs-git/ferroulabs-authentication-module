"""Convert db_session fixture tests to dual_session async pattern.

For each target file:
1. Replace db_session with dual_session in function signatures
2. Add sync_db, async_db = dual_session at start
3. Replace db_session.xxx() calls with sync_db.xxx() for setup
4. Add await to known async service function calls  
5. Add @pytest.mark.asyncio + async def
"""
import re
from pathlib import Path

# Map of file → list of async service function names that need await
FILE_ASYNC_FUNCTIONS = {
    "test_user_suspension.py": [
        "suspend_user", "unsuspend_user", "get_user_by_id",
    ],
    "test_cleanup_service.py": [
        "purge_expired_refresh_tokens", "purge_stale_invitations",
        "purge_old_rate_limit_hits", "purge_old_audit_events", "run_cleanup",
    ],
    "test_space_service.py": [
        "create_space", "list_user_spaces", "list_account_spaces",
        "get_space_by_id", "update_space", "suspend_space", "unsuspend_space",
    ],
    "test_membership_backfill.py": [],  # May not have async calls
}

tests_dir = Path(__file__).parent

for fname, async_fns in FILE_ASYNC_FUNCTIONS.items():
    fpath = tests_dir / fname
    if not fpath.exists():
        print(f"SKIP {fname}: not found")
        continue

    content = fpath.read_text(encoding="utf-8")
    original = content

    # Step 1: Replace db_session fixture in function signatures
    # Pattern: def test_xxx(db_session) or def test_xxx(db_session, monkeypatch)
    def replace_test_def(m):
        indent = m.group(1)
        name = m.group(2)
        params = m.group(3)
        # Replace db_session with dual_session in params
        new_params = params.replace("db_session", "dual_session")
        return f"{indent}@pytest.mark.asyncio\n{indent}async def {name}({new_params}):"
    
    content = re.sub(
        r'^(\s*)def (test_\w+)\(([^)]*db_session[^)]*)\):',
        replace_test_def,
        content,
        flags=re.MULTILINE,
    )

    # Step 2: After each "async def test_xxx(dual_session..." line, 
    # check if next non-empty line has the unpack and add one if not
    lines = content.split("\n")
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        new_lines.append(line)
        
        # Check if this line is an async test function with dual_session
        if re.match(r'\s*async def test_\w+\(.*dual_session.*\):', line):
            indent = re.match(r'(\s*)', line).group(1) + "    "
            # Check if next non-empty, non-docstring line already has the unpack
            j = i + 1
            # Skip docstring
            while j < len(lines):
                stripped = lines[j].strip()
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    # Find end of docstring
                    if stripped.count('"""') >= 2 or stripped.count("'''") >= 2:
                        j += 1
                        break
                    j += 1
                    while j < len(lines):
                        if '"""' in lines[j] or "'''" in lines[j]:
                            j += 1
                            break
                        j += 1
                    break
                elif stripped == "":
                    j += 1
                    continue
                else:
                    break
            
            # Check if unpack line already exists
            has_unpack = False
            if j < len(lines) and "sync_db, async_db = dual_session" in lines[j]:
                has_unpack = True
            
            if not has_unpack:
                # Add docstring lines first, then insert unpack
                # Actually, we need to add it right after the def line (and any docstring)
                # For simplicity, add lines up to j, then insert unpack
                while i + 1 < j:
                    i += 1
                    new_lines.append(lines[i])
                new_lines.append(f"{indent}sync_db, async_db = dual_session")
        
        i += 1
    
    content = "\n".join(new_lines)

    # Step 3: Replace db_session.xxx() with sync_db.xxx()
    content = content.replace("db_session.add(", "sync_db.add(")
    content = content.replace("db_session.add_all(", "sync_db.add_all(")
    content = content.replace("db_session.commit(", "sync_db.commit(")
    content = content.replace("db_session.refresh(", "sync_db.refresh(")
    content = content.replace("db_session.query(", "sync_db.query(")
    content = content.replace("db_session.close(", "sync_db.close(")
    content = content.replace("db_session.flush(", "sync_db.flush(")

    # Step 4: Replace service calls with await + async_db
    # Pattern: fn_name(..., db_session) → await fn_name(..., async_db)
    for fn_name in async_fns:
        # Replace db_session in service call args
        # Pattern: fn_name(args, db_session) or fn_name(db_session) 
        content = re.sub(
            rf'(?<!\bawait )({fn_name}\([^)]*)\bdb_session\b',
            lambda m: "await " + m.group(1) + "async_db",
            content,
        )
        # Also handle cases where db_session was already replaced to dual_session
        content = re.sub(
            rf'(?<!\bawait )({fn_name}\([^)]*)\bdual_session\b',
            lambda m: "await " + m.group(1) + "async_db",
            content,
        )

    if content != original:
        fpath.write_text(content, encoding="utf-8")
        print(f"CONVERTED {fname}")
    else:
        print(f"NOCHANGE {fname}")

print("\nDone!")
