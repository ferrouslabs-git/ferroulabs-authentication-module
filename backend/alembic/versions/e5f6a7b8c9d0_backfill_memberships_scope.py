"""backfill_memberships_scope

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-20 00:00:05.000000

Data migration: populates new scope columns from old tenant_id/role values.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Backfill memberships
    op.execute("""
        UPDATE memberships
        SET scope_type = 'account',
            scope_id = tenant_id,
            role_name = CASE role
                WHEN 'owner'  THEN 'account_owner'
                WHEN 'admin'  THEN 'account_admin'
                WHEN 'member' THEN 'account_member'
                WHEN 'viewer' THEN 'space_viewer'
            END
        WHERE scope_type IS NULL AND tenant_id IS NOT NULL
    """)

    # Backfill invitations
    op.execute("""
        UPDATE invitations
        SET target_scope_type = 'account',
            target_scope_id = tenant_id,
            target_role_name = CASE role
                WHEN 'owner'  THEN 'account_owner'
                WHEN 'admin'  THEN 'account_admin'
                WHEN 'member' THEN 'account_member'
                WHEN 'viewer' THEN 'space_viewer'
            END
        WHERE target_scope_type IS NULL AND tenant_id IS NOT NULL
    """)


def downgrade() -> None:
    # Clear backfilled columns
    op.execute("UPDATE memberships SET scope_type = NULL, scope_id = NULL, role_name = NULL")
    op.execute("""
        UPDATE invitations
        SET target_scope_type = NULL, target_scope_id = NULL, target_role_name = NULL
    """)
