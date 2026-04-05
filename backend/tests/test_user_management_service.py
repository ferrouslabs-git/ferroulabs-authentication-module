"""Unit tests for tenant user-management service."""

from uuid import uuid4

import pytest

from app.auth_usermanagement.models.membership import Membership
from app.auth_usermanagement.models.tenant import Tenant
from app.auth_usermanagement.models.user import User
from app.auth_usermanagement.services.user_management_service import (
    list_tenant_users,
    list_platform_users,
    update_user_role,
    remove_user_from_tenant,
)


def _seed_tenant_with_users(sync_db):
    tenant = Tenant(name="Acme")
    owner_user = User(cognito_sub="owner-sub", email="owner@example.com", name="Owner")
    admin_user = User(cognito_sub="admin-sub", email="admin@example.com", name="Admin")
    member_user = User(cognito_sub="member-sub", email="member@example.com", name="Member")

    sync_db.add_all([tenant, owner_user, admin_user, member_user])
    sync_db.flush()

    owner_membership = Membership(
        user_id=owner_user.id,
        scope_type="account",
        scope_id=tenant.id,
        role_name="owner",
        status="active",
    )
    admin_membership = Membership(
        user_id=admin_user.id,
        scope_type="account",
        scope_id=tenant.id,
        role_name="admin",
        status="active",
    )
    member_membership = Membership(
        user_id=member_user.id,
        scope_type="account",
        scope_id=tenant.id,
        role_name="member",
        status="active",
    )

    sync_db.add_all([owner_membership, admin_membership, member_membership])
    sync_db.commit()

    return {
        "tenant_id": tenant.id,
        "owner_user_id": owner_user.id,
        "admin_user_id": admin_user.id,
        "member_user_id": member_user.id,
    }


@pytest.mark.asyncio
async def test_admin_can_only_assign_member_or_viewer(dual_session):
    sync_db, async_db = dual_session
    ids = _seed_tenant_with_users(sync_db)

    with pytest.raises(ValueError, match="Admins can only assign member or viewer roles"):
        await update_user_role(
            async_db,
            ids["tenant_id"],
            ids["member_user_id"],
            "admin",
            actor_role="admin",
            actor_is_platform_admin=False,
        )


@pytest.mark.asyncio
async def test_admin_cannot_modify_owner_roles(dual_session):
    sync_db, async_db = dual_session
    ids = _seed_tenant_with_users(sync_db)

    with pytest.raises(ValueError, match="Admins cannot modify owner roles"):
        await update_user_role(
            async_db,
            ids["tenant_id"],
            ids["owner_user_id"],
            "member",
            actor_role="admin",
            actor_is_platform_admin=False,
        )


@pytest.mark.asyncio
async def test_owner_can_promote_member_to_admin(dual_session):
    sync_db, async_db = dual_session
    ids = _seed_tenant_with_users(sync_db)

    membership = await update_user_role(
        async_db,
        ids["tenant_id"],
        ids["member_user_id"],
        "admin",
        actor_role="owner",
        actor_is_platform_admin=False,
    )

    assert membership is not None
    assert membership.role_name == "admin"


# ── list_tenant_users ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_tenant_users_returns_active_members(dual_session):
    sync_db, async_db = dual_session
    ids = _seed_tenant_with_users(sync_db)

    users = await list_tenant_users(async_db, ids["tenant_id"])
    assert len(users) == 3
    emails = {u["email"] for u in users}
    assert "owner@example.com" in emails
    assert "admin@example.com" in emails
    assert "member@example.com" in emails
    assert all(u["status"] == "active" for u in users)


@pytest.mark.asyncio
async def test_list_tenant_users_excludes_removed_members(dual_session):
    sync_db, async_db = dual_session
    ids = _seed_tenant_with_users(sync_db)

    m = sync_db.query(Membership).filter(
        Membership.user_id == ids["member_user_id"],
        Membership.scope_id == ids["tenant_id"],
    ).first()
    m.status = "removed"
    sync_db.commit()

    users = await list_tenant_users(async_db, ids["tenant_id"])
    assert len(users) == 2
    emails = {u["email"] for u in users}
    assert "member@example.com" not in emails


@pytest.mark.asyncio
async def test_list_tenant_users_empty_for_unknown_tenant(dual_session):
    sync_db, async_db = dual_session
    _seed_tenant_with_users(sync_db)

    users = await list_tenant_users(async_db, uuid4())
    assert users == []


# ── list_platform_users ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_platform_users_returns_all_users_sorted(dual_session):
    sync_db, async_db = dual_session
    _seed_tenant_with_users(sync_db)

    users = await list_platform_users(async_db)
    assert len(users) == 3
    emails = [u["email"] for u in users]
    assert emails == sorted(emails)
    assert all("memberships" in u for u in users)


# ── remove_user_from_tenant ─────────────────────────────────────


@pytest.mark.asyncio
async def test_remove_user_from_tenant_sets_removed_status(dual_session):
    sync_db, async_db = dual_session
    ids = _seed_tenant_with_users(sync_db)

    membership = await remove_user_from_tenant(async_db, ids["tenant_id"], ids["member_user_id"])
    assert membership is not None
    assert membership.status == "removed"


@pytest.mark.asyncio
async def test_remove_user_returns_none_for_nonexistent(dual_session):
    sync_db, async_db = dual_session
    ids = _seed_tenant_with_users(sync_db)

    result = await remove_user_from_tenant(async_db, ids["tenant_id"], uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_remove_last_owner_raises(dual_session):
    sync_db, async_db = dual_session
    ids = _seed_tenant_with_users(sync_db)

    with pytest.raises(ValueError, match="Cannot remove last owner"):
        await remove_user_from_tenant(async_db, ids["tenant_id"], ids["owner_user_id"])


# ── update_user_role edge cases ──────────────────────────────────


@pytest.mark.asyncio
async def test_update_role_returns_none_for_nonexistent_membership(dual_session):
    sync_db, async_db = dual_session
    ids = _seed_tenant_with_users(sync_db)

    result = await update_user_role(async_db, ids["tenant_id"], uuid4(), "admin", actor_role="owner")
    assert result is None


@pytest.mark.asyncio
async def test_platform_admin_can_modify_owner_role(dual_session):
    sync_db, async_db = dual_session
    ids = _seed_tenant_with_users(sync_db)

    second_owner = User(cognito_sub="owner2-sub", email="owner2@example.com", name="Owner 2")
    sync_db.add(second_owner)
    sync_db.flush()
    sync_db.add(Membership(
        user_id=second_owner.id, scope_type="account", scope_id=ids["tenant_id"],
        role_name="account_owner", status="active",
    ))
    sync_db.commit()

    membership = await update_user_role(
        async_db, ids["tenant_id"], ids["owner_user_id"],
        "member", actor_role=None, actor_is_platform_admin=True,
    )
    assert membership.role_name == "member"


@pytest.mark.asyncio
async def test_demote_last_owner_raises(dual_session):
    sync_db, async_db = dual_session
    ids = _seed_tenant_with_users(sync_db)

    with pytest.raises(ValueError, match="Cannot remove last owner"):
        await update_user_role(
            async_db, ids["tenant_id"], ids["owner_user_id"],
            "member", actor_role="owner", actor_is_platform_admin=True,
        )
