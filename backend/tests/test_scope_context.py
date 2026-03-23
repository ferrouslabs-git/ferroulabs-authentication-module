"""Tests for get_scope_context dependency (Task 4)."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.database import Base
from app.auth_usermanagement.models.membership import Membership
from app.auth_usermanagement.models.space import Space
from app.auth_usermanagement.models.tenant import Tenant
from app.auth_usermanagement.models.user import User
from app.auth_usermanagement.security.dependencies import (
    get_scope_context,
    get_tenant_context,
)
from app.auth_usermanagement.services.auth_config_loader import reset_auth_config


# ── Helpers ──────────────────────────────────────────────────────


def _make_request(headers: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "path": "/test",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "query_string": b"",
    }
    return Request(scope)


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def _reset_config():
    reset_auth_config()
    yield
    reset_auth_config()


def _make_user(db, *, platform_admin=False, email_prefix="user"):
    user = User(
        cognito_sub=f"sub-{email_prefix}-{uuid4().hex[:8]}",
        email=f"{email_prefix}-{uuid4().hex[:8]}@test.com",
        name="Test User",
        is_platform_admin=platform_admin,
    )
    db.add(user)
    db.flush()
    return user


def _make_account(db, name="Test Account"):
    tenant = Tenant(name=name)
    db.add(tenant)
    db.flush()
    return tenant


def _make_space(db, account_id, name="Test Space"):
    space = Space(name=name, account_id=account_id)
    db.add(space)
    db.flush()
    return space


# ── Account scope tests ─────────────────────────────────────────


def test_account_scope_with_new_headers(test_db):
    """X-Scope-Type: account + X-Scope-ID resolves correct permissions."""
    user = _make_user(test_db)
    account = _make_account(test_db)
    test_db.add(Membership(
        user_id=user.id,
        scope_type="account",
        scope_id=account.id,
        role_name="account_owner",
        status="active",
    ))
    test_db.commit()

    request = _make_request({
        "X-Scope-Type": "account",
        "X-Scope-ID": str(account.id),
    })
    ctx = get_scope_context(request, user, test_db)

    assert ctx.scope_type == "account"
    assert ctx.scope_id == account.id
    assert "account_owner" in ctx.active_roles
    assert ctx.has_permission("account:delete")
    assert ctx.has_permission("members:manage")
    assert not ctx.is_super_admin


def test_tenant_id_header_resolves_account_scope(test_db):
    """X-Tenant-ID header resolves as scope_type=account."""
    user = _make_user(test_db)
    account = _make_account(test_db)
    test_db.add(Membership(
        user_id=user.id,
        scope_type="account",
        scope_id=account.id,
        role_name="account_owner",
        status="active",
    ))
    test_db.commit()

    request = _make_request({"X-Tenant-ID": str(account.id)})
    ctx = get_scope_context(request, user, test_db)

    assert ctx.scope_type == "account"
    assert ctx.scope_id == account.id
    assert "account_owner" in ctx.active_roles
    assert ctx.has_permission("account:delete")


# ── Space scope tests ───────────────────────────────────────────


def test_space_scope_direct_membership(test_db):
    """Space-scope request resolves permissions from space memberships."""
    user = _make_user(test_db)
    account = _make_account(test_db)
    space = _make_space(test_db, account.id)
    test_db.add(Membership(
        user_id=user.id,
        scope_type="space",
        scope_id=space.id,
        role_name="space_member",
        status="active",
    ))
    test_db.commit()

    request = _make_request({
        "X-Scope-Type": "space",
        "X-Scope-ID": str(space.id),
    })
    ctx = get_scope_context(request, user, test_db)

    assert ctx.scope_type == "space"
    assert ctx.scope_id == space.id
    assert "space_member" in ctx.active_roles
    assert ctx.has_permission("data:read")
    assert ctx.has_permission("data:write")
    assert not ctx.has_permission("space:delete")


# ── Inheritance tests ────────────────────────────────────────────


def test_inheritance_account_owner_gets_space_admin(test_db):
    """account_owner inherits space_admin permissions when requesting space scope."""
    user = _make_user(test_db)
    account = _make_account(test_db)
    space = _make_space(test_db, account.id)
    # Only account-level membership, no space membership
    test_db.add(Membership(
        user_id=user.id,
        scope_type="account",
        scope_id=account.id,
        role_name="account_owner",
        status="active",
    ))
    test_db.commit()

    request = _make_request({
        "X-Scope-Type": "space",
        "X-Scope-ID": str(space.id),
    })
    ctx = get_scope_context(request, user, test_db)

    assert "space_admin" in ctx.active_roles
    assert ctx.has_permission("space:delete")
    assert ctx.has_permission("data:read")
    assert ctx.has_permission("data:write")
    assert ctx.has_permission("members:manage")


def test_inheritance_account_admin_gets_space_member(test_db):
    """account_admin inherits space_member permissions."""
    user = _make_user(test_db)
    account = _make_account(test_db)
    space = _make_space(test_db, account.id)
    test_db.add(Membership(
        user_id=user.id,
        scope_type="account",
        scope_id=account.id,
        role_name="account_admin",
        status="active",
    ))
    test_db.commit()

    request = _make_request({
        "X-Scope-Type": "space",
        "X-Scope-ID": str(space.id),
    })
    ctx = get_scope_context(request, user, test_db)

    assert "space_member" in ctx.active_roles
    assert ctx.has_permission("data:read")
    assert ctx.has_permission("data:write")
    assert not ctx.has_permission("space:delete")


def test_inheritance_account_member_gets_nothing_by_default(test_db):
    """account_member gets nothing by default (config: none)."""
    user = _make_user(test_db)
    account = _make_account(test_db)
    space = _make_space(test_db, account.id)
    test_db.add(Membership(
        user_id=user.id,
        scope_type="account",
        scope_id=account.id,
        role_name="account_member",
        status="active",
    ))
    test_db.commit()

    request = _make_request({
        "X-Scope-Type": "space",
        "X-Scope-ID": str(space.id),
    })

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        get_scope_context(request, user, test_db)
    assert exc_info.value.status_code == 403


# ── Super admin tests ────────────────────────────────────────────


def test_super_admin_bypasses_membership_check(test_db):
    """super_admin can access any scope without membership."""
    admin = _make_user(test_db, platform_admin=True, email_prefix="admin")
    account = _make_account(test_db)
    # No membership created

    request = _make_request({
        "X-Scope-Type": "account",
        "X-Scope-ID": str(account.id),
    })
    ctx = get_scope_context(request, admin, test_db)

    assert ctx.is_super_admin is True
    assert ctx.scope_id == account.id
    assert ctx.has_permission("anything:at_all")  # super_admin bypasses


def test_platform_admin_space_access_without_membership(test_db):
    """Platform admin can access space scope without any membership."""
    admin = _make_user(test_db, platform_admin=True, email_prefix="padmin")
    account = _make_account(test_db)
    space = _make_space(test_db, account.id)

    request = _make_request({
        "X-Scope-Type": "space",
        "X-Scope-ID": str(space.id),
    })
    ctx = get_scope_context(request, admin, test_db)

    assert ctx.is_super_admin is True
    assert ctx.scope_type == "space"


# ── Error cases ──────────────────────────────────────────────────


def test_missing_scope_headers_returns_400(test_db):
    """Missing scope headers → 400."""
    user = _make_user(test_db)
    test_db.commit()

    request = _make_request({})

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        get_scope_context(request, user, test_db)
    assert exc_info.value.status_code == 400
    assert "Scope headers required" in exc_info.value.detail


def test_invalid_scope_type_returns_400(test_db):
    """Invalid X-Scope-Type → 400."""
    user = _make_user(test_db)
    test_db.commit()

    request = _make_request({
        "X-Scope-Type": "galaxy",
        "X-Scope-ID": str(uuid4()),
    })

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        get_scope_context(request, user, test_db)
    assert exc_info.value.status_code == 400
    assert "Invalid X-Scope-Type" in exc_info.value.detail


def test_invalid_scope_id_format_returns_400(test_db):
    """Invalid UUID in scope ID → 400."""
    user = _make_user(test_db)
    test_db.commit()

    request = _make_request({
        "X-Scope-Type": "account",
        "X-Scope-ID": "not-a-uuid",
    })

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        get_scope_context(request, user, test_db)
    assert exc_info.value.status_code == 400
    assert "Invalid scope ID" in exc_info.value.detail


def test_no_membership_returns_403(test_db):
    """No membership in scope → 403 for non-admin."""
    user = _make_user(test_db)
    account = _make_account(test_db)
    test_db.commit()
    # No membership

    request = _make_request({
        "X-Scope-Type": "account",
        "X-Scope-ID": str(account.id),
    })

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        get_scope_context(request, user, test_db)
    assert exc_info.value.status_code == 403
    assert "Access denied" in exc_info.value.detail


# ── Caching test ─────────────────────────────────────────────────


def test_scope_context_cached_on_request_state(test_db):
    """Second call returns cached ScopeContext from request.state."""
    user = _make_user(test_db)
    account = _make_account(test_db)
    test_db.add(Membership(
        user_id=user.id,
        scope_type="account",
        scope_id=account.id,
        role_name="account_admin",
        status="active",
    ))
    test_db.commit()

    request = _make_request({
        "X-Scope-Type": "account",
        "X-Scope-ID": str(account.id),
    })
    ctx1 = get_scope_context(request, user, test_db)
    ctx2 = get_scope_context(request, user, test_db)

    assert ctx1 is ctx2


# ── Deprecated get_tenant_context wrapper ────────────────────────


def test_deprecated_tenant_context_wraps_scope_context(test_db):
    """get_tenant_context returns TenantContext via get_scope_context."""
    user = _make_user(test_db)
    account = _make_account(test_db)
    test_db.add(Membership(
        user_id=user.id,
        scope_type="account",
        scope_id=account.id,
        role_name="account_owner",
        status="active",
    ))
    test_db.commit()

    request = _make_request({"X-Tenant-ID": str(account.id)})
    ctx = get_tenant_context(request, user, test_db)

    assert ctx.tenant_id == account.id
    assert ctx.role == "owner"
    assert ctx.user_id == user.id
    assert not ctx.is_platform_admin


def test_deprecated_tenant_context_platform_admin(test_db):
    """Platform admin via deprecated wrapper gets is_platform_admin=True."""
    admin = _make_user(test_db, platform_admin=True, email_prefix="dep-admin")
    account = _make_account(test_db)
    test_db.commit()

    request = _make_request({"X-Tenant-ID": str(account.id)})
    ctx = get_tenant_context(request, admin, test_db)

    assert ctx.is_platform_admin is True
    assert ctx.role is None  # no membership
