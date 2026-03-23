"""Unit tests for ScopeContext and TenantContext dataclass methods."""

from uuid import uuid4

from app.auth_usermanagement.security.scope_context import ScopeContext
from app.auth_usermanagement.security.tenant_context import TenantContext


# ── ScopeContext ─────────────────────────────────────────────────


def test_has_permission_returns_true_when_present():
    ctx = ScopeContext(
        user_id=uuid4(), scope_type="account", scope_id=uuid4(),
        active_roles=["account_admin"],
        resolved_permissions={"members:manage", "data:read"},
    )
    assert ctx.has_permission("members:manage") is True


def test_has_permission_returns_false_when_absent():
    ctx = ScopeContext(
        user_id=uuid4(), scope_type="account", scope_id=uuid4(),
        active_roles=["account_member"],
        resolved_permissions={"data:read"},
    )
    assert ctx.has_permission("members:manage") is False


def test_has_permission_super_admin_always_true():
    ctx = ScopeContext(
        user_id=uuid4(), scope_type="account", scope_id=uuid4(),
        is_super_admin=True,
    )
    assert ctx.has_permission("anything:here") is True


def test_has_any_permission_true_if_one_matches():
    ctx = ScopeContext(
        user_id=uuid4(), scope_type="account", scope_id=uuid4(),
        resolved_permissions={"data:read"},
    )
    assert ctx.has_any_permission(["members:manage", "data:read"]) is True


def test_has_any_permission_false_if_none_match():
    ctx = ScopeContext(
        user_id=uuid4(), scope_type="account", scope_id=uuid4(),
        resolved_permissions={"data:read"},
    )
    assert ctx.has_any_permission(["members:manage", "billing:manage"]) is False


def test_has_any_permission_super_admin():
    ctx = ScopeContext(
        user_id=uuid4(), scope_type="account", scope_id=uuid4(),
        is_super_admin=True,
    )
    assert ctx.has_any_permission(["anything"]) is True


def test_has_all_permissions_true():
    ctx = ScopeContext(
        user_id=uuid4(), scope_type="account", scope_id=uuid4(),
        resolved_permissions={"a", "b", "c"},
    )
    assert ctx.has_all_permissions(["a", "b"]) is True


def test_has_all_permissions_false_when_partial():
    ctx = ScopeContext(
        user_id=uuid4(), scope_type="account", scope_id=uuid4(),
        resolved_permissions={"a"},
    )
    assert ctx.has_all_permissions(["a", "b"]) is False


def test_has_all_permissions_super_admin():
    ctx = ScopeContext(
        user_id=uuid4(), scope_type="account", scope_id=uuid4(),
        is_super_admin=True,
    )
    assert ctx.has_all_permissions(["x", "y", "z"]) is True


def test_has_any_permission_empty_list():
    ctx = ScopeContext(
        user_id=uuid4(), scope_type="account", scope_id=uuid4(),
        resolved_permissions={"a"},
    )
    assert ctx.has_any_permission([]) is False


def test_has_all_permissions_empty_list():
    ctx = ScopeContext(
        user_id=uuid4(), scope_type="account", scope_id=uuid4(),
        resolved_permissions=set(),
    )
    assert ctx.has_all_permissions([]) is True


def test_scope_context_defaults():
    ctx = ScopeContext(user_id=uuid4(), scope_type="platform", scope_id=None)
    assert ctx.active_roles == []
    assert ctx.resolved_permissions == set()
    assert ctx.is_super_admin is False


# ── TenantContext ────────────────────────────────────────────────


def test_can_access_tenant_with_role():
    ctx = TenantContext(user_id=uuid4(), tenant_id=uuid4(), role="member", is_platform_admin=False)
    assert ctx.can_access_tenant() is True


def test_can_access_tenant_as_platform_admin():
    ctx = TenantContext(user_id=uuid4(), tenant_id=uuid4(), role=None, is_platform_admin=True)
    assert ctx.can_access_tenant() is True


def test_cannot_access_tenant_without_role_or_admin():
    ctx = TenantContext(user_id=uuid4(), tenant_id=uuid4(), role=None, is_platform_admin=False)
    assert ctx.can_access_tenant() is False


def test_is_owner():
    ctx = TenantContext(user_id=uuid4(), tenant_id=uuid4(), role="owner", is_platform_admin=False)
    assert ctx.is_owner() is True


def test_is_not_owner():
    ctx = TenantContext(user_id=uuid4(), tenant_id=uuid4(), role="admin", is_platform_admin=False)
    assert ctx.is_owner() is False


def test_is_admin_or_owner():
    for role in ("owner", "admin"):
        ctx = TenantContext(user_id=uuid4(), tenant_id=uuid4(), role=role, is_platform_admin=False)
        assert ctx.is_admin_or_owner() is True


def test_is_not_admin_or_owner():
    ctx = TenantContext(user_id=uuid4(), tenant_id=uuid4(), role="member", is_platform_admin=False)
    assert ctx.is_admin_or_owner() is False
