"""force rls on tenant tables

Revision ID: 4f2a1e9c7b10
Revises: 2a9b67c1d3ef
Create Date: 2026-03-17 12:10:00.000000
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "4f2a1e9c7b10"
down_revision: Union[str, Sequence[str], None] = "2a9b67c1d3ef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Force RLS so table owners do not bypass tenant isolation policies."""
    op.execute("ALTER TABLE memberships FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE invitations FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    """Revert forced RLS owner restriction."""
    op.execute("ALTER TABLE memberships NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE invitations NO FORCE ROW LEVEL SECURITY")
