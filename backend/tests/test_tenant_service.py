"""Unit tests for tenant service — create, lookup, access, list."""

from uuid import uuid4

import pytest

from app.auth_usermanagement.models.membership import Membership
from app.auth_usermanagement.models.tenant import Tenant
from app.auth_usermanagement.models.user import User
from app.auth_usermanagement.services.tenant_service import (
    create_tenant,
    get_tenant_by_id,
    get_user_tenants,
    get_user_tenant_role,
    list_platform_tenants,
    suspend_tenant,
    unsuspend_tenant,
    verify_user_tenant_access,
)


# ── create_tenant ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_tenant_assigns_owner_membership(dual_session):
    sync_db, async_db = dual_session
    user = User(cognito_sub="sub-1", email="creator@example.com", name="Creator")
    sync_db.add(user)
    sync_db.commit()

    tenant = await create_tenant("Acme", user, async_db)

    assert tenant.name == "Acme"
    assert tenant.status == "active"
    assert tenant.plan == "free"

    await async_db.commit()
    sync_db.expire_all()
    membership = sync_db.query(Membership).filter(
        Membership.scope_id == tenant.id,
        Membership.user_id == user.id,
    ).first()
    assert membership is not None
    assert membership.scope_type == "account"
    assert membership.role_name == "account_owner"
    assert membership.status == "active"


@pytest.mark.asyncio
async def test_create_tenant_with_custom_plan(dual_session):
    sync_db, async_db = dual_session
    user = User(cognito_sub="sub-2", email="u@example.com", name="U")
    sync_db.add(user)
    sync_db.commit()

    tenant = await create_tenant("Beta", user, async_db, plan="pro")
    assert tenant.plan == "pro"


# ── get_tenant_by_id ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_tenant_by_id_found(dual_session):
    sync_db, async_db = dual_session
    tenant = Tenant(name="Found")
    sync_db.add(tenant)
    sync_db.commit()

    result = await get_tenant_by_id(tenant.id, async_db)
    assert result is not None
    assert result.name == "Found"


@pytest.mark.asyncio
async def test_get_tenant_by_id_not_found(dual_session):
    sync_db, async_db = dual_session
    result = await get_tenant_by_id(uuid4(), async_db)
    assert result is None


# ── get_user_tenants ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_user_tenants_returns_active_account_memberships(dual_session):
    sync_db, async_db = dual_session
    user = User(cognito_sub="sub-3", email="multi@example.com", name="Multi")
    t1 = Tenant(name="T1")
    t2 = Tenant(name="T2")
    sync_db.add_all([user, t1, t2])
    sync_db.commit()

    sync_db.add_all([
        Membership(user_id=user.id, scope_type="account", scope_id=t1.id,
                   role_name="account_owner", status="active"),
        Membership(user_id=user.id, scope_type="account", scope_id=t2.id,
                   role_name="account_member", status="active"),
    ])
    sync_db.commit()

    tenants = await get_user_tenants(user.id, async_db)
    assert len(tenants) == 2
    names = {t["name"] for t in tenants}
    assert names == {"T1", "T2"}


@pytest.mark.asyncio
async def test_get_user_tenants_excludes_removed_memberships(dual_session):
    sync_db, async_db = dual_session
    user = User(cognito_sub="sub-4", email="removed@example.com", name="Rem")
    t = Tenant(name="T")
    sync_db.add_all([user, t])
    sync_db.commit()

    sync_db.add(Membership(user_id=user.id, scope_type="account", scope_id=t.id,
                          role_name="account_member", status="removed"))
    sync_db.commit()

    tenants = await get_user_tenants(user.id, async_db)
    assert tenants == []


@pytest.mark.asyncio
async def test_get_user_tenants_excludes_space_memberships(dual_session):
    sync_db, async_db = dual_session
    user = User(cognito_sub="sub-5", email="space@example.com", name="S")
    t = Tenant(name="T")
    sync_db.add_all([user, t])
    sync_db.commit()

    sync_db.add(Membership(user_id=user.id, scope_type="space", scope_id=uuid4(),
                          role_name="space_member", status="active"))
    sync_db.commit()

    tenants = await get_user_tenants(user.id, async_db)
    assert tenants == []


# ── get_user_tenant_role ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_user_tenant_role_returns_role_name(dual_session):
    sync_db, async_db = dual_session
    user = User(cognito_sub="sub-6", email="role@example.com", name="R")
    t = Tenant(name="T")
    sync_db.add_all([user, t])
    sync_db.commit()

    sync_db.add(Membership(user_id=user.id, scope_type="account", scope_id=t.id,
                          role_name="account_admin", status="active"))
    sync_db.commit()

    role = await get_user_tenant_role(user.id, t.id, async_db)
    assert role == "account_admin"


@pytest.mark.asyncio
async def test_get_user_tenant_role_returns_none_when_no_membership(dual_session):
    sync_db, async_db = dual_session
    role = await get_user_tenant_role(uuid4(), uuid4(), async_db)
    assert role is None


# ── verify_user_tenant_access ────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_access_true_for_active_member(dual_session):
    sync_db, async_db = dual_session
    user = User(cognito_sub="sub-7", email="access@example.com", name="A")
    t = Tenant(name="T")
    sync_db.add_all([user, t])
    sync_db.commit()

    sync_db.add(Membership(user_id=user.id, scope_type="account", scope_id=t.id,
                          role_name="account_member", status="active"))
    sync_db.commit()

    assert await verify_user_tenant_access(user.id, t.id, async_db) is True


@pytest.mark.asyncio
async def test_verify_access_false_for_removed_member(dual_session):
    sync_db, async_db = dual_session
    user = User(cognito_sub="sub-8", email="no@example.com", name="N")
    t = Tenant(name="T")
    sync_db.add_all([user, t])
    sync_db.commit()

    sync_db.add(Membership(user_id=user.id, scope_type="account", scope_id=t.id,
                          role_name="account_member", status="removed"))
    sync_db.commit()

    assert await verify_user_tenant_access(user.id, t.id, async_db) is False


@pytest.mark.asyncio
async def test_verify_access_false_for_no_membership(dual_session):
    sync_db, async_db = dual_session
    assert await verify_user_tenant_access(uuid4(), uuid4(), async_db) is False


# ── list_platform_tenants ────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_platform_tenants_includes_counts(dual_session):
    sync_db, async_db = dual_session
    t = Tenant(name="Acme", status="active")
    u1 = User(cognito_sub="s1", email="a@x.com", name="A")
    u2 = User(cognito_sub="s2", email="b@x.com", name="B")
    sync_db.add_all([t, u1, u2])
    sync_db.commit()

    sync_db.add_all([
        Membership(user_id=u1.id, scope_type="account", scope_id=t.id,
                   role_name="account_owner", status="active"),
        Membership(user_id=u2.id, scope_type="account", scope_id=t.id,
                   role_name="account_member", status="active"),
    ])
    sync_db.commit()

    tenants = await list_platform_tenants(async_db)
    assert len(tenants) == 1
    assert tenants[0]["name"] == "Acme"
    assert tenants[0]["member_count"] == 2
    assert tenants[0]["owner_count"] == 1


@pytest.mark.asyncio
async def test_list_platform_tenants_excludes_removed_from_counts(dual_session):
    sync_db, async_db = dual_session
    t = Tenant(name="T", status="active")
    u = User(cognito_sub="s", email="e@x.com", name="N")
    sync_db.add_all([t, u])
    sync_db.commit()

    sync_db.add(Membership(user_id=u.id, scope_type="account", scope_id=t.id,
                          role_name="account_member", status="removed"))
    sync_db.commit()

    tenants = await list_platform_tenants(async_db)
    assert tenants[0]["member_count"] == 0


# ── suspend / unsuspend ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_suspend_nonexistent_tenant_raises(dual_session):
    sync_db, async_db = dual_session
    with pytest.raises(ValueError, match="Tenant not found"):
        await suspend_tenant(uuid4(), async_db)


@pytest.mark.asyncio
async def test_unsuspend_nonexistent_tenant_raises(dual_session):
    sync_db, async_db = dual_session
    with pytest.raises(ValueError, match="Tenant not found"):
        await unsuspend_tenant(uuid4(), async_db)
