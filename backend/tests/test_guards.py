"""Unit tests for role guard behavior."""
import warnings
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.auth_usermanagement.security.guards import require_admin, require_min_role
from app.auth_usermanagement.security.tenant_context import TenantContext


def _ctx(role: str | None, is_platform_admin: bool = False) -> TenantContext:
    return TenantContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        role=role,
        is_platform_admin=is_platform_admin,
    )


def test_require_admin_allows_owner_and_admin():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        assert require_admin(_ctx("owner")).role == "owner"
        assert require_admin(_ctx("admin")).role == "admin"


def test_require_admin_blocks_member():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        with pytest.raises(HTTPException) as exc:
            require_admin(_ctx("member"))

    assert exc.value.status_code == 403
    assert "permission" in str(exc.value.detail).lower() or "role" in str(exc.value.detail).lower()


def test_require_admin_allows_platform_admin_regardless_of_role():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        result = require_admin(_ctx(None, is_platform_admin=True))
    assert result.is_platform_admin is True


def test_tenant_context_helpers_allow_platform_admin_without_membership_role():
    ctx = _ctx(None, is_platform_admin=True)

    assert ctx.can_access_tenant() is True
    assert ctx.is_owner() is False
    assert ctx.is_admin_or_owner() is False


def test_require_min_role_rejects_invalid_role_name():
    with pytest.raises(ValueError):
        require_min_role("superuser")
