"""replace_memberships_schema

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-20 00:00:03.000000

Adds new scope columns to memberships. Keeps old tenant_id/role columns
for backward compatibility until the deprecation window closes (Task 12).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # New columns (nullable initially — backfill in migration 15)
    op.add_column('memberships', sa.Column('role_name', sa.String(100), nullable=True))
    op.add_column('memberships', sa.Column('scope_type', sa.String(20), nullable=True))
    op.add_column('memberships', sa.Column('scope_id', sa.Uuid(), nullable=True))
    op.add_column('memberships', sa.Column('granted_by', sa.Uuid(),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))

    op.create_index('ix_memberships_scope_id', 'memberships', ['scope_id'])

    # Make old columns nullable (so new code can omit them)
    op.alter_column('memberships', 'tenant_id', nullable=True)
    op.alter_column('memberships', 'role', nullable=True)

    # Swap constraints: drop old, add new
    op.drop_constraint('unique_user_tenant', 'memberships', type_='unique')
    op.create_unique_constraint(
        'unique_user_role_scope',
        'memberships',
        ['user_id', 'role_name', 'scope_type', 'scope_id'],
    )


def downgrade() -> None:
    op.drop_constraint('unique_user_role_scope', 'memberships', type_='unique')
    op.create_unique_constraint('unique_user_tenant', 'memberships', ['user_id', 'tenant_id'])

    op.alter_column('memberships', 'role', nullable=False)
    op.alter_column('memberships', 'tenant_id', nullable=False)

    op.drop_index('ix_memberships_scope_id', 'memberships')
    op.drop_column('memberships', 'granted_by')
    op.drop_column('memberships', 'scope_id')
    op.drop_column('memberships', 'scope_type')
    op.drop_column('memberships', 'role_name')
