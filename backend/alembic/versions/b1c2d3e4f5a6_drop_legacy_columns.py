"""drop legacy columns

Revision ID: b1c2d3e4f5a6
Revises: a7b8c9d0e1f2
Create Date: 2026-03-20 16:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop deprecated columns and tighten nullability on scope columns.

    Memberships: drop tenant_id (FK), drop role; make scope_type, scope_id,
    role_name NOT NULL.

    Invitations: drop role; make target_scope_type, target_scope_id,
    target_role_name NOT NULL.
    """

    # ── Memberships ─────────────────────────────────────────────────
    op.drop_constraint(
        "memberships_tenant_id_fkey", "memberships", type_="foreignkey"
    )
    op.drop_column("memberships", "tenant_id")
    op.drop_column("memberships", "role")
    op.alter_column("memberships", "scope_type", nullable=False)
    op.alter_column("memberships", "scope_id", nullable=False)
    op.alter_column("memberships", "role_name", nullable=False)

    # ── Invitations ─────────────────────────────────────────────────
    op.drop_column("invitations", "role")
    op.alter_column("invitations", "target_scope_type", nullable=False)
    op.alter_column("invitations", "target_scope_id", nullable=False)
    op.alter_column("invitations", "target_role_name", nullable=False)


def downgrade() -> None:
    """Restore deprecated columns."""

    # ── Invitations ─────────────────────────────────────────────────
    op.alter_column("invitations", "target_role_name", nullable=True)
    op.alter_column("invitations", "target_scope_id", nullable=True)
    op.alter_column("invitations", "target_scope_type", nullable=True)
    op.add_column(
        "invitations",
        sa.Column("role", sa.String(20), nullable=True),
    )

    # ── Memberships ─────────────────────────────────────────────────
    op.alter_column("memberships", "role_name", nullable=True)
    op.alter_column("memberships", "scope_id", nullable=True)
    op.alter_column("memberships", "scope_type", nullable=True)
    op.add_column(
        "memberships",
        sa.Column("role", sa.String(20), nullable=True),
    )
    op.add_column(
        "memberships",
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "memberships_tenant_id_fkey",
        "memberships",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
