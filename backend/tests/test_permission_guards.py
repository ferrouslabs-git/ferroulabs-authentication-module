"""Tests for the v3.0 permission-based guard system."""
import warnings
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.auth_usermanagement.security.guards import (
    require_permission,
    require_any_permission,
    require_all_permissions,
    require_super_admin,
    require_admin,
    require_viewer,
    require_owner,
    require_member,
    check_permission,
    _bridge_to_scope,
)
from app.auth_usermanagement.security.tenant_context import TenantContext
from app.auth_usermanagement.security.scope_context import ScopeContext


# ── Helpers ──────────────────────────────────────────────────────

def _tenant_ctx(role: str | None = None, is_platform_admin: bool = False) -> TenantContext:
    return TenantContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        role=role,
        is_platform_admin=is_platform_admin,
    )


def _scope_ctx(
    permissions: set[str] | None = None,
    is_super_admin: bool = False,
    roles: list[str] | None = None,
) -> ScopeContext:
    return ScopeContext(
        user_id=uuid4(),
        scope_type="account",
        scope_id=uuid4(),
        active_roles=roles or [],
        resolved_permissions=permissions or set(),
        is_super_admin=is_super_admin,
    )


# ── Bridge tests ─────────────────────────────────────────────────

def test_bridge_owner_gets_expected_permissions():
    ctx = _tenant_ctx(role="owner")
    scope = _bridge_to_scope(ctx)
    assert "account:delete" in scope.resolved_permissions
    assert "members:manage" in scope.resolved_permissions
    assert "data:read" in scope.resolved_permissions


def test_bridge_viewer_gets_read_permissions():
    ctx = _tenant_ctx(role="viewer")
    scope = _bridge_to_scope(ctx)
    assert "data:read" in scope.resolved_permissions
    assert "data:write" not in scope.resolved_permissions
    assert "members:manage" not in scope.resolved_permissions


def test_bridge_platform_admin_sets_super_admin():
    ctx = _tenant_ctx(role=None, is_platform_admin=True)
    scope = _bridge_to_scope(ctx)
    assert scope.is_super_admin is True
    assert scope.resolved_permissions == set()  # no role → no permissions
    assert scope.has_permission("anything")  # super_admin bypasses


# ── require_permission ───────────────────────────────────────────

def test_require_permission_passes_when_present():
    checker = require_permission("data:read")
    ctx = _scope_ctx(permissions={"data:read", "account:read"}, roles=["account_member"])
    result = checker(ctx)
    assert isinstance(result, ScopeContext)
    assert "data:read" in result.resolved_permissions


def test_require_permission_blocks_when_absent():
    checker = require_permission("account:delete")
    ctx = _scope_ctx(permissions={"data:read"}, roles=["account_member"])
    with pytest.raises(HTTPException) as exc:
        checker(ctx)
    assert exc.value.status_code == 403
    assert "account:delete" in exc.value.detail


def test_require_permission_passes_for_super_admin():
    checker = require_permission("account:delete")
    ctx = _scope_ctx(is_super_admin=True)
    result = checker(ctx)
    assert result.is_super_admin is True


# ── require_any_permission ───────────────────────────────────────

def test_require_any_permission_passes_if_one_present():
    checker = require_any_permission(["data:read", "data:write"])
    ctx = _scope_ctx(permissions={"data:read"}, roles=["account_member"])
    result = checker(ctx)
    assert result is not None


def test_require_any_permission_blocks_if_none_present():
    checker = require_any_permission(["account:delete", "spaces:create"])
    ctx = _scope_ctx(permissions={"data:read"}, roles=["account_member"])
    with pytest.raises(HTTPException) as exc:
        checker(ctx)
    assert exc.value.status_code == 403


# ── require_all_permissions ──────────────────────────────────────

def test_require_all_permissions_passes_when_all_present():
    checker = require_all_permissions(["data:read", "data:write"])
    ctx = _scope_ctx(permissions={"data:read", "data:write"}, roles=["account_member"])
    result = checker(ctx)
    assert result is not None


def test_require_all_permissions_blocks_when_only_some():
    checker = require_all_permissions(["data:read", "members:manage"])
    ctx = _scope_ctx(permissions={"data:read"}, roles=["account_member"])
    with pytest.raises(HTTPException) as exc:
        checker(ctx)
    assert exc.value.status_code == 403


# ── require_super_admin ──────────────────────────────────────────

def test_require_super_admin_passes():
    ctx = _scope_ctx(is_super_admin=True)
    result = require_super_admin(ctx)
    assert result.is_super_admin is True


def test_require_super_admin_blocks_normal_user():
    ctx = _scope_ctx(permissions={"account:delete"}, roles=["account_owner"])
    with pytest.raises(HTTPException) as exc:
        require_super_admin(ctx)
    assert exc.value.status_code == 403


# ── ScopeContext.role_name property ──────────────────────────────

def test_scope_context_role_name_returns_first_role():
    ctx = _scope_ctx(roles=["account_owner", "account_admin"])
    assert ctx.role_name == "account_owner"


def test_scope_context_role_name_none_when_empty():
    ctx = _scope_ctx(roles=[])
    assert ctx.role_name is None


# ── Deprecated wrappers still work ───────────────────────────────

def test_deprecated_require_admin_passes_for_owner():
    ctx = _tenant_ctx(role="owner")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = require_admin(ctx)
        assert result.role == "owner"
        assert any("deprecated" in str(warning.message).lower() for warning in w)


def test_deprecated_require_admin_passes_for_admin():
    ctx = _tenant_ctx(role="admin")
    result = require_admin(ctx)
    assert result.role == "admin"


def test_deprecated_require_admin_blocks_viewer():
    ctx = _tenant_ctx(role="viewer")
    with pytest.raises(HTTPException) as exc:
        require_admin(ctx)
    assert exc.value.status_code == 403


def test_deprecated_require_viewer_passes_for_viewer():
    ctx = _tenant_ctx(role="viewer")
    result = require_viewer(ctx)
    assert result.role == "viewer"


def test_deprecated_require_owner_passes_for_owner():
    ctx = _tenant_ctx(role="owner")
    result = require_owner(ctx)
    assert result.role == "owner"


def test_deprecated_require_owner_blocks_admin():
    ctx = _tenant_ctx(role="admin")
    with pytest.raises(HTTPException) as exc:
        require_owner(ctx)
    assert exc.value.status_code == 403


def test_deprecated_require_member_passes_for_member():
    ctx = _tenant_ctx(role="member")
    result = require_member(ctx)
    assert result.role == "member"


def test_deprecated_require_member_blocks_viewer():
    ctx = _tenant_ctx(role="viewer")
    with pytest.raises(HTTPException) as exc:
        require_member(ctx)
    assert exc.value.status_code == 403


def test_deprecated_require_admin_passes_for_platform_admin():
    ctx = _tenant_ctx(role=None, is_platform_admin=True)
    result = require_admin(ctx)
    assert result.is_platform_admin is True


# ── check_permission (deprecated) ────────────────────────────────

def test_deprecated_check_permission_owner_has_data_read():
    ctx = _tenant_ctx(role="owner")
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        assert check_permission(ctx, "data:read") is True


def test_deprecated_check_permission_viewer_lacks_members_manage():
    ctx = _tenant_ctx(role="viewer")
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        assert check_permission(ctx, "members:manage") is False


# ── Guards never check role name strings ─────────────────────────

def test_guards_use_permissions_not_role_names():
    """New guards check resolved_permissions, not role name strings."""
    scope = _scope_ctx(permissions={"data:read"}, roles=["custom_role"])
    # The bridge isn't used here — directly verify ScopeContext behavior
    assert scope.has_permission("data:read") is True
    assert scope.has_permission("data:write") is False
    # The role name "custom_role" doesn't matter for permission checks
    assert scope.active_roles == ["custom_role"]
