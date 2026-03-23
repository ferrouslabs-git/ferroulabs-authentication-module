"""seed_role_definitions

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-03-20 00:00:06.000000

Reads auth_config.yaml and populates role_definitions + permission_grants.
"""
from typing import Sequence, Union
from datetime import datetime
import os
from pathlib import Path

from alembic import op
import sqlalchemy as sa
import yaml


revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STRUCTURAL_PERMISSIONS = frozenset({
    "platform:configure", "accounts:manage", "account:delete", "account:read",
    "spaces:create", "space:delete", "space:configure", "space:read",
    "members:manage", "members:invite", "users:suspend",
})


def _load_config() -> dict:
    config_path = os.getenv(
        "AUTH_CONFIG_PATH",
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "app", "auth_usermanagement", "auth_config.yaml",
        ),
    )
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def upgrade() -> None:
    raw = _load_config()
    now = datetime.utcnow()

    role_defs = sa.table(
        'role_definitions',
        sa.column('name', sa.String),
        sa.column('layer', sa.String),
        sa.column('display_name', sa.String),
        sa.column('is_builtin', sa.Boolean),
        sa.column('created_at', sa.DateTime),
    )
    perm_grants = sa.table(
        'permission_grants',
        sa.column('role_name', sa.String),
        sa.column('permission', sa.String),
        sa.column('permission_type', sa.String),
    )

    for layer_name in ("platform", "account", "space"):
        for role in raw.get("roles", {}).get(layer_name, []):
            op.bulk_insert(role_defs, [{
                "name": role["name"],
                "layer": layer_name,
                "display_name": role["display_name"],
                "is_builtin": True,
                "created_at": now,
            }])
            for perm in role.get("permissions", []):
                perm_type = "structural" if perm in STRUCTURAL_PERMISSIONS else "product"
                op.bulk_insert(perm_grants, [{
                    "role_name": role["name"],
                    "permission": perm,
                    "permission_type": perm_type,
                }])


def downgrade() -> None:
    op.execute("DELETE FROM permission_grants")
    op.execute("DELETE FROM role_definitions")
