"""Unit tests for role guard behavior."""
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.auth_usermanagement.security.guards import require_admin, require_min_role
from app.auth_usermanagement.security.tenant_context import TenantContext


def _ctx(role: str, is_platform_admin: bool = False) -> TenantContext:
    return TenantContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        role=role,
        is_platform_admin=is_platform_admin,
    )


def test_require_admin_allows_owner_and_admin():
    assert require_admin(_ctx("owner")).role == "owner"
    assert require_admin(_ctx("admin")).role == "admin"


def test_require_admin_blocks_member():
    with pytest.raises(HTTPException) as exc:
        require_admin(_ctx("member"))

    assert exc.value.status_code == 403
    assert "Required role" in str(exc.value.detail)


def test_require_admin_allows_platform_admin_regardless_of_role():
    result = require_admin(_ctx("viewer", is_platform_admin=True))
    assert result.is_platform_admin is True


def test_require_min_role_rejects_invalid_role_name():
    with pytest.raises(ValueError):
        require_min_role("superuser")
