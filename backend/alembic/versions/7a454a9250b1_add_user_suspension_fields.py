"""add_user_suspension_fields

Revision ID: 7a454a9250b1
Revises: d3494139f54d
Create Date: 2026-03-08 19:41:28.994978

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a454a9250b1'
down_revision: Union[str, Sequence[str], None] = 'd3494139f54d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add is_active column (default True for existing users)
    op.add_column('users', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))
    # Add suspended_at column (nullable)
    op.add_column('users', sa.Column('suspended_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove suspension fields
    op.drop_column('users', 'suspended_at')
    op.drop_column('users', 'is_active')
