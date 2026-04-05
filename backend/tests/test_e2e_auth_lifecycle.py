"""End-to-end auth lifecycle tests.

These tests exercise full user journeys across the auth system:
- Full auth lifecycle (sync → membership → profile → session)
- Multi-tenant isolation
- RBAC escalation prevention
- Session security lifecycle
"""
from datetime import datetime, timedelta, UTC
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth_usermanagement.api.auth_routes import router as auth_router
from app.auth_usermanagement.models.invitation import Invitation
from app.auth_usermanagement.models.membership import Membership
from app.auth_usermanagement.models.session import Session as AuthSession
from app.auth_usermanagement.models.space import Space
from app.auth_usermanagement.models.tenant import Tenant
from app.auth_usermanagement.models.user import User
from app.auth_usermanagement.schemas.token import TokenPayload
from app.auth_usermanagement.security.scope_context import ScopeContext
from app.auth_usermanagement.services.invitation_service import (
    accept_invitation,
    create_invitation,
)
from app.auth_usermanagement.services.session_service import (
    create_user_session,
    list_user_sessions,
)
from app.auth_usermanagement.services.space_service import create_space
from app.auth_usermanagement.services.user_service import (
    sync_user_from_cognito,
    get_user_by_cognito_sub,
    suspend_user,
)
from app.database import Base
from tests.async_test_utils import make_test_db, make_async_app


# ── Helpers ──────────────────────────────────────────────────────

def _utc_now():
    return datetime.now(UTC).replace(tzinfo=None)


def _make_db():
    return make_test_db()


# ── E2E: Full auth lifecycle ─────────────────────────────────────


class TestFullAuthLifecycle:
    @patch("app.auth_usermanagement.api.auth_routes.verify_token_async")
    def test_sync_then_profile_then_memberships(self, mock_verify):
        """
        Simulate: user logs in via Cognito → syncs to DB → gets profile → gets memberships.
        """
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        try:
            mock_verify.return_value = TokenPayload(
                sub="e2e-sub-1", email="e2e@lifecycle.test", name="E2E User",
                exp=99999999999, iat=1000000000, token_use="id", aud="test-client",
            )

            # Override get_current_user to use our DB
            from app.auth_usermanagement.security.dependencies import get_current_user, verify_token as dep_verify
            with patch("app.auth_usermanagement.security.dependencies.verify_token_async") as dep_mock:
                dep_mock.return_value = TokenPayload(
                    sub="e2e-sub-1", email="e2e@lifecycle.test",
                    exp=99999999999, iat=1000000000, token_use="access", client_id="test",
                )

                app = make_async_app(auth_router, async_engine, AsyncSessionLocal, prefix="/auth")
                client = TestClient(app)

                # Step 1: Sync user
                resp = client.post("/auth/sync", headers={"Authorization": "Bearer e2e-token"})
                assert resp.status_code == 200
                user_data = resp.json()
                assert user_data["cognito_sub"] == "e2e-sub-1"
                user_id = user_data["user_id"]

                # Step 2: Get profile
                resp = client.get("/auth/me", headers={"Authorization": "Bearer e2e-token"})
                assert resp.status_code == 200
                assert resp.json()["email"] == "e2e@lifecycle.test"

                # Step 3: Create membership via direct DB (simulating invitation acceptance)
                session = SyncSession()
                tenant = Tenant(name="E2E Corp")
                session.add(tenant)
                session.commit()
                user = session.query(User).filter(User.cognito_sub == "e2e-sub-1").first()
                session.add(Membership(
                    user_id=user.id, scope_type="account", scope_id=tenant.id,
                    role_name="account_member", status="active",
                ))
                session.commit()
                session.close()

                # Step 4: Get memberships
                resp = client.get("/auth/me/memberships", headers={"Authorization": "Bearer e2e-token"})
                assert resp.status_code == 200
                memberships = resp.json()
                assert len(memberships) == 1
                assert memberships[0]["scope_type"] == "account"
                assert memberships[0]["tenant_name"] == "E2E Corp"
        finally:
            Base.metadata.drop_all(sync_engine)


# ── E2E: Multi-tenant isolation ──────────────────────────────────


class TestMultiTenantIsolation:
    def test_user_membership_isolation(self, db_session):
        """Users should only see memberships for their own accounts."""
        t1 = Tenant(name="Tenant A")
        t2 = Tenant(name="Tenant B")
        user_a = User(cognito_sub="iso-a", email="a@iso.test", name="A")
        user_b = User(cognito_sub="iso-b", email="b@iso.test", name="B")
        db_session.add_all([t1, t2, user_a, user_b])
        db_session.commit()

        db_session.add(Membership(
            user_id=user_a.id, scope_type="account", scope_id=t1.id,
            role_name="account_admin", status="active",
        ))
        db_session.add(Membership(
            user_id=user_b.id, scope_type="account", scope_id=t2.id,
            role_name="account_member", status="active",
        ))
        db_session.commit()

        a_memberships = db_session.query(Membership).filter(
            Membership.user_id == user_a.id, Membership.status == "active"
        ).all()
        assert len(a_memberships) == 1
        assert a_memberships[0].scope_id == t1.id

        b_memberships = db_session.query(Membership).filter(
            Membership.user_id == user_b.id, Membership.status == "active"
        ).all()
        assert len(b_memberships) == 1
        assert b_memberships[0].scope_id == t2.id

    @pytest.mark.asyncio
    async def test_invitation_scoped_to_tenant(self, dual_session):
        """Invitation acceptance should only create membership in the invited tenant."""
        sync_db, async_db = dual_session
        t1 = Tenant(name="Invited Corp")
        t2 = Tenant(name="Other Corp")
        inviter = User(cognito_sub="inv-a", email="inv@multi.test", name="Inv")
        invitee = User(cognito_sub="inv-b", email="invitee@multi.test", name="Invitee")
        sync_db.add_all([t1, t2, inviter, invitee])
        sync_db.commit()

        # Invite to t1 only
        invitation, _ = await create_invitation(
            db=async_db, tenant_id=t1.id, email=invitee.email,
            role="member", created_by=inviter.id,
        )
        await accept_invitation(async_db, invitation, invitee)
        await async_db.commit()

        # Should have membership in t1 only
        sync_db.expire_all()
        memberships = sync_db.query(Membership).filter(
            Membership.user_id == invitee.id
        ).all()
        assert len(memberships) == 1
        assert memberships[0].scope_id == t1.id

        # No membership in t2
        t2_membership = sync_db.query(Membership).filter(
            Membership.user_id == invitee.id,
            Membership.scope_id == t2.id,
        ).first()
        assert t2_membership is None


# ── E2E: RBAC escalation prevention ─────────────────────────────


class TestRBACEscalationPrevention:
    def test_scope_context_super_admin_bypass(self):
        """Platform admin should bypass all permission checks."""
        admin_id = uuid4()
        ctx = ScopeContext(
            user_id=admin_id, scope_type="platform", scope_id=uuid4(),
            is_super_admin=True,
        )
        assert ctx.has_permission("anything:at:all") is True
        assert ctx.has_any_permission(["x", "y"]) is True
        assert ctx.has_all_permissions(["a", "b", "c"]) is True

    def test_regular_user_cannot_elevate_permissions(self):
        """Non-admin user should only have their granted permissions."""
        user_id = uuid4()
        ctx = ScopeContext(
            user_id=user_id, scope_type="account", scope_id=uuid4(),
            active_roles=["account_member"],
            resolved_permissions={"account:read", "members:list"},
            is_super_admin=False,
        )
        assert ctx.has_permission("account:read") is True
        assert ctx.has_permission("account:delete") is False
        assert ctx.has_permission("members:invite") is False

    def test_has_any_permission(self):
        ctx = ScopeContext(
            user_id=uuid4(), scope_type="account", scope_id=uuid4(),
            resolved_permissions={"account:read"},
        )
        assert ctx.has_any_permission(["account:read", "account:write"]) is True
        assert ctx.has_any_permission(["account:delete"]) is False

    def test_has_all_permissions(self):
        ctx = ScopeContext(
            user_id=uuid4(), scope_type="account", scope_id=uuid4(),
            resolved_permissions={"account:read", "account:write"},
        )
        assert ctx.has_all_permissions(["account:read", "account:write"]) is True
        assert ctx.has_all_permissions(["account:read", "account:delete"]) is False


# ── E2E: Session security lifecycle ──────────────────────────────


class TestSessionSecurityLifecycle:
    @pytest.mark.asyncio
    async def test_create_and_list_sessions(self, dual_session):
        sync_db, async_db = dual_session
        user = User(cognito_sub="sess-sub", email="sess@test.com", name="Sess")
        sync_db.add(user)
        sync_db.commit()

        s1 = await create_user_session(
            async_db, user.id, "refresh-token-1",
            user_agent="Chrome", ip_address="10.0.0.1",
        )
        s2 = await create_user_session(
            async_db, user.id, "refresh-token-2",
            user_agent="Firefox", ip_address="10.0.0.2",
        )

        active = await list_user_sessions(async_db, user.id)
        assert len(active) == 2

    @pytest.mark.asyncio
    async def test_revoke_session(self, dual_session):
        sync_db, async_db = dual_session
        user = User(cognito_sub="rev-sub", email="rev@test.com", name="Rev")
        sync_db.add(user)
        sync_db.commit()

        auth_sess = await create_user_session(async_db, user.id, "revoke-me")
        assert auth_sess.is_revoked is False

        auth_sess.revoke()
        await async_db.commit()
        assert auth_sess.is_revoked is True

        # Revoked sessions excluded by default
        active = await list_user_sessions(async_db, user.id)
        assert len(active) == 0

        # But accessible with include_revoked
        all_sessions = await list_user_sessions(async_db, user.id, include_revoked=True)
        assert len(all_sessions) == 1

    @pytest.mark.asyncio
    @patch("app.auth_usermanagement.services.user_service._cognito_global_sign_out")
    async def test_suspend_user_invalidates_sessions_conceptually(self, mock_signout, dual_session):
        """Suspending a user should trigger Cognito global sign-out."""
        sync_db, async_db = dual_session
        user = User(cognito_sub="susp-sess", email="susp-sess@test.com", name="SS")
        sync_db.add(user)
        sync_db.commit()

        await create_user_session(async_db, user.id, "active-token")

        await suspend_user(user.id, async_db)
        mock_signout.assert_called_once_with("susp-sess")

        await async_db.commit()
        sync_db.expire_all()
        sync_db.refresh(user)
        assert user.is_active is False


# ── E2E: Sync idempotency ───────────────────────────────────────


class TestSyncIdempotency:
    @pytest.mark.asyncio
    async def test_sync_creates_then_updates_user(self, dual_session):
        sync_db, async_db = dual_session

        payload = TokenPayload(
            sub="sync-sub", email="sync@test.com", name="Initial",
            exp=99999999999, iat=1000000000, token_use="access",
        )
        user = await sync_user_from_cognito(payload, async_db)
        assert user.email == "sync@test.com"
        assert user.name == "Initial"

        # Sync again with updated name
        payload2 = TokenPayload(
            sub="sync-sub", email="sync@test.com", name="Updated",
            exp=99999999999, iat=1000000000, token_use="access",
        )
        user2 = await sync_user_from_cognito(payload2, async_db)
        assert user2.id == user.id
        assert user2.name == "Updated"

    @pytest.mark.asyncio
    async def test_sync_handles_cognito_recreation(self, dual_session):
        """When Cognito user is deleted and recreated with same email but new sub."""
        sync_db, async_db = dual_session

        # First sync
        p1 = TokenPayload(
            sub="old-sub", email="recreate@test.com",
            exp=99999999999, iat=1000000000, token_use="access",
        )
        user1 = await sync_user_from_cognito(p1, async_db)

        # Same email, new sub
        p2 = TokenPayload(
            sub="new-sub", email="recreate@test.com",
            exp=99999999999, iat=1000000000, token_use="access",
        )
        user2 = await sync_user_from_cognito(p2, async_db)

        assert user2.id == user1.id
        assert user2.cognito_sub == "new-sub"

    @pytest.mark.asyncio
    async def test_sync_rejects_missing_email(self, dual_session):
        sync_db, async_db = dual_session
        payload = TokenPayload(
            sub="no-email-sub", exp=99999999999, iat=1000000000, token_use="access",
        )
        with pytest.raises(ValueError, match="email"):
            await sync_user_from_cognito(payload, async_db)
            Base.metadata.drop_all(sync_engine)
