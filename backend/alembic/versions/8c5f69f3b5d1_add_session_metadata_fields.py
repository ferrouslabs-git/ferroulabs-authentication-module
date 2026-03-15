"""add session metadata fields

Revision ID: 8c5f69f3b5d1
Revises: 0eec64567dac
Create Date: 2026-03-15 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8c5f69f3b5d1"
down_revision: Union[str, Sequence[str], None] = "0eec64567dac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("sessions", sa.Column("user_agent", sa.String(length=512), nullable=True))
    op.add_column("sessions", sa.Column("ip_address", sa.String(length=64), nullable=True))
    op.add_column("sessions", sa.Column("device_info", sa.String(length=255), nullable=True))
    op.add_column("sessions", sa.Column("expires_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("sessions", "expires_at")
    op.drop_column("sessions", "device_info")
    op.drop_column("sessions", "ip_address")
    op.drop_column("sessions", "user_agent")
