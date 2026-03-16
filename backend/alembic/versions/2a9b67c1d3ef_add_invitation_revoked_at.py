"""add invitation revoked_at

Revision ID: 2a9b67c1d3ef
Revises: f1c2d3e4a5b6
Create Date: 2026-03-16 19:58:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2a9b67c1d3ef"
down_revision = "f1c2d3e4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invitations", sa.Column("revoked_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("invitations", "revoked_at")
