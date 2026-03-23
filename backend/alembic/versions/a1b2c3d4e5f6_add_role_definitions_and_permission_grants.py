"""add_role_definitions_and_permission_grants_tables

Revision ID: a1b2c3d4e5f6
Revises: 9f2e1c7a4b3d
Create Date: 2026-03-20 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '9f2e1c7a4b3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'role_definitions',
        sa.Column('name', sa.String(100), primary_key=True),
        sa.Column('layer', sa.String(20), nullable=False),
        sa.Column('display_name', sa.String(255), nullable=False),
        sa.Column('is_builtin', sa.Boolean(), server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'permission_grants',
        sa.Column('role_name', sa.String(100),
                  sa.ForeignKey('role_definitions.name'), primary_key=True),
        sa.Column('permission', sa.String(200), primary_key=True, nullable=False),
        sa.Column('permission_type', sa.String(20), nullable=False),
        sa.UniqueConstraint('role_name', 'permission', name='unique_role_permission'),
    )


def downgrade() -> None:
    op.drop_table('permission_grants')
    op.drop_table('role_definitions')
