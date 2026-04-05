"""Cross-feature integration tests.

These tests exercise interactions across multiple service boundaries:
invitation → acceptance → membership, space invitations, authority escalation,
suspended user/tenant denial, deletion cascades, and bulk invitations.
"""
from datetime import datetime, timedelta, UTC
from unittest.mock import patch, MagicMock
from uuid import uuid4

import pytest

from app.auth_usermanagement.models.invitation import Invitation
from app.auth_usermanagement.models.membership import Membership
from app.auth_usermanagement.models.session import Session as AuthSession
from app.auth_usermanagement.models.space import Space
from app.auth_usermanagement.models.tenant import Tenant
from app.auth_usermanagement.models.user import User
from app.auth_usermanagement.services.invitation_service import (
    accept_invitation,
    create_invitation,
    get_invitation_by_token,
    hash_token,
)
from app.auth_usermanagement.services.space_service import create_space
from app.auth_usermanagement.services.user_service import (
    suspend_user,
    unsuspend_user,
)


# ── Helpers ──────────────────────────────────────────────────────

def _utc_now():
    return datetime.now(UTC).replace(tzinfo=None)


def _seed_tenant_and_users(session, n_users=2):
    """Create a tenant and n_users, return (tenant, [users])."""
    tenant = Tenant(name="IntegrationCo")
    session.add(tenant)
    session.flush()

    users = []
    for i in range(n_users):
        u = User(
            cognito_sub=f"int-sub-{i}",
            email=f"user{i}@integration.test",
            name=f"User {i}",
        )
        session.add(u)
        users.append(u)
    session.commit()
    return tenant, users


# ── Invitation → Acceptance → Membership ────────────────────────


class TestInvitationAcceptanceFlow:
    @pytest.mark.asyncio
    async def test_full_invitation_to_membership(self, dual_session):
        """Create invitation, look up by token, accept it, verify membership."""
        sync_db, async_db = dual_session
        tenant, users = _seed_tenant_and_users(sync_db)
        inviter, invitee = users[0], users[1]

        # Inviter creates invitation for invitee
        invitation, raw_token = await create_invitation(
            db=async_db,
            tenant_id=tenant.id,
            email=invitee.email,
            role="member",
            created_by=inviter.id,
            target_scope_type="account",
            target_scope_id=tenant.id,
        )
        assert invitation.status == "pending"

        # Look up by token
        found = await get_invitation_by_token(async_db, raw_token)
        assert found is not None
        assert found.id == invitation.id

        # Accept
        membership = await accept_invitation(async_db, found, invitee)
        assert membership.user_id == invitee.id
        assert membership.scope_type == "account"
        assert membership.scope_id == tenant.id
        assert membership.status == "active"

        # Invitation is now accepted
        await async_db.refresh(invitation)
        assert invitation.status == "accepted"

    @pytest.mark.asyncio
    async def test_accept_invitation_rejects_expired(self, dual_session):
        sync_db, async_db = dual_session
        tenant, users = _seed_tenant_and_users(sync_db)

        invitation, raw_token = await create_invitation(
            db=async_db,
            tenant_id=tenant.id,
            email=users[1].email,
            role="member",
            created_by=users[0].id,
            expires_in_days=0,  # Already expired
        )
        # Force expiration
        invitation.expires_at = _utc_now() - timedelta(hours=1)
        await async_db.commit()

        with pytest.raises(ValueError, match="expired"):
            await accept_invitation(async_db, invitation, users[1])

    @pytest.mark.asyncio
    async def test_accept_invitation_email_mismatch(self, dual_session):
        sync_db, async_db = dual_session
        tenant, users = _seed_tenant_and_users(sync_db)

        invitation, _ = await create_invitation(
            db=async_db,
            tenant_id=tenant.id,
            email="other@example.com",
            role="member",
            created_by=users[0].id,
        )

        with pytest.raises(PermissionError, match="does not match"):
            await accept_invitation(async_db, invitation, users[1])

    @pytest.mark.asyncio
    async def test_accept_invitation_double_accept(self, dual_session):
        sync_db, async_db = dual_session
        tenant, users = _seed_tenant_and_users(sync_db)

        invitation, _ = await create_invitation(
            db=async_db,
            tenant_id=tenant.id,
            email=users[1].email,
            role="member",
            created_by=users[0].id,
        )
        await accept_invitation(async_db, invitation, users[1])

        with pytest.raises(ValueError, match="already been accepted"):
            await accept_invitation(async_db, invitation, users[1])

    @pytest.mark.asyncio
    async def test_new_invitation_revokes_previous_pending(self, dual_session):
        """Creating a new invitation for the same email should revoke old pending ones."""
        sync_db, async_db = dual_session
        tenant, users = _seed_tenant_and_users(sync_db)

        inv1, tok1 = await create_invitation(
            db=async_db, tenant_id=tenant.id, email=users[1].email,
            role="member", created_by=users[0].id,
        )
        inv2, tok2 = await create_invitation(
            db=async_db, tenant_id=tenant.id, email=users[1].email,
            role="admin", created_by=users[0].id,
        )

        await async_db.refresh(inv1)
        assert inv1.status == "revoked" or inv1.status == "expired"
        assert inv2.status == "pending"


# ── Space invitation + membership ────────────────────────────────


class TestSpaceInvitationFlow:
    @pytest.mark.asyncio
    async def test_space_invitation_creates_space_membership(self, dual_session):
        sync_db, async_db = dual_session
        tenant, users = _seed_tenant_and_users(sync_db)

        space = await create_space(async_db, "Dev Team", tenant.id, users[0].id)

        invitation, raw_token = await create_invitation(
            db=async_db,
            tenant_id=tenant.id,
            email=users[1].email,
            role="member",
            created_by=users[0].id,
            target_scope_type="space",
            target_scope_id=space.id,
            target_role_name="space_member",
        )

        membership = await accept_invitation(async_db, invitation, users[1])
        assert membership.scope_type == "space"
        assert membership.scope_id == space.id
        assert membership.role_name == "space_member"


# ── Suspended user rejection ────────────────────────────────────


class TestSuspendedUserBehavior:
    @pytest.mark.asyncio
    @patch("app.auth_usermanagement.services.user_service._cognito_global_sign_out")
    async def test_suspend_then_unsuspend_user(self, mock_signout, dual_session):
        sync_db, async_db = dual_session
        user = User(cognito_sub="susp-sub", email="susp@test.com", name="Susp")
        sync_db.add(user)
        sync_db.commit()

        suspended = await suspend_user(user.id, async_db)
        assert suspended.is_active is False
        assert suspended.suspended_at is not None
        mock_signout.assert_called_once()

        unsuspended = await unsuspend_user(user.id, async_db)
        assert unsuspended.is_active is True

    @pytest.mark.asyncio
    @patch("app.auth_usermanagement.services.user_service._cognito_global_sign_out")
    async def test_suspend_user_not_found(self, mock_signout, dual_session):
        sync_db, async_db = dual_session
        with pytest.raises(ValueError, match="not found"):
            await suspend_user(uuid4(), async_db)


# ── Tenant deletion cascade ─────────────────────────────────────


class TestTenantDeletionCascade:
    @pytest.mark.asyncio
    async def test_deleting_tenant_cascades_invitations(self, dual_session):
        """When a tenant is deleted, its invitations should cascade-delete."""
        sync_db, async_db = dual_session
        tenant, users = _seed_tenant_and_users(sync_db, n_users=1)

        await create_invitation(
            db=async_db, tenant_id=tenant.id, email="cascade@test.com",
            role="member", created_by=users[0].id,
        )
        await async_db.commit()

        sync_db.expire_all()
        assert sync_db.query(Invitation).count() == 1

        sync_db.delete(tenant)
        sync_db.commit()

        assert sync_db.query(Invitation).count() == 0


# ── Membership re-invite does not downgrade ──────────────────────


class TestMembershipNoDowngrade:
    @pytest.mark.asyncio
    async def test_accepting_lower_role_keeps_higher_role(self, dual_session):
        """
        If user already has account_admin, accepting an account_member
        invite should NOT downgrade them.
        """
        sync_db, async_db = dual_session
        tenant, users = _seed_tenant_and_users(sync_db)

        # Give user1 an existing admin membership
        sync_db.add(Membership(
            user_id=users[1].id, scope_type="account",
            scope_id=tenant.id, role_name="account_admin", status="active",
        ))
        sync_db.commit()

        # Create a "member" invitation for the same user
        invitation, _ = await create_invitation(
            db=async_db, tenant_id=tenant.id, email=users[1].email,
            role="member", created_by=users[0].id,
            target_role_name="account_member",
        )

        membership = await accept_invitation(async_db, invitation, users[1])
        # account_member perms are a subset of account_admin,
        # so the role should stay account_admin
        assert membership.role_name == "account_admin"
        assert membership.status == "active"


# ── User deletion cascade ───────────────────────────────────────


class TestUserDeletionCascade:
    @pytest.mark.asyncio
    @patch("app.auth_usermanagement.services.cognito_admin_service.admin_delete_user")
    async def test_delete_user_removes_memberships_and_sessions(self, mock_cognito, dual_session):
        from app.auth_usermanagement.services.user_service import delete_user

        mock_cognito.return_value = {"deleted": True}
        sync_db, async_db = dual_session
        tenant = Tenant(name="DelCo")
        user = User(cognito_sub="del-c-sub", email="delc@test.com", name="Del")
        sync_db.add_all([tenant, user])
        sync_db.commit()

        sync_db.add(Membership(
            user_id=user.id, scope_type="account", scope_id=tenant.id,
            role_name="account_member", status="active",
        ))
        sync_db.add(AuthSession(user_id=user.id, refresh_token_hash="hash123"))
        sync_db.commit()
        uid = user.id

        result = await delete_user(uid, async_db)
        assert result["deleted"] is True
        await async_db.commit()

        sync_db.expire_all()
        assert sync_db.query(User).filter(User.id == uid).first() is None
        assert sync_db.query(Membership).filter(Membership.user_id == uid).count() == 0
        assert sync_db.query(AuthSession).filter(AuthSession.user_id == uid).count() == 0
