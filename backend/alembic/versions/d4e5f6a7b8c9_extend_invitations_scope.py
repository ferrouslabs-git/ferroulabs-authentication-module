"""extend_invitations_scope

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-20 00:00:04.000000

Adds target_scope_type, target_scope_id, target_role_name to invitations
so invitations can target any scope layer (account or space).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('invitations', sa.Column('target_scope_type', sa.String(20), nullable=True))
    op.add_column('invitations', sa.Column('target_scope_id', sa.Uuid(), nullable=True))
    op.add_column('invitations', sa.Column('target_role_name', sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column('invitations', 'target_role_name')
    op.drop_column('invitations', 'target_scope_id')
    op.drop_column('invitations', 'target_scope_type')
