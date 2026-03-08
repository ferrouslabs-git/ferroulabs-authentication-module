"""enable_row_level_security

Revision ID: 0eec64567dac
Revises: 7a454a9250b1
Create Date: 2026-03-08 19:48:55.408138

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0eec64567dac'
down_revision: Union[str, Sequence[str], None] = '7a454a9250b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Enable Row-Level Security on tenant-scoped tables."""
    
    # Enable RLS on invitations table
    op.execute("ALTER TABLE invitations ENABLE ROW LEVEL SECURITY")
    
    # Policy: Allow access if tenant_id matches session variable OR user is platform admin
    op.execute("""
        CREATE POLICY invitations_tenant_isolation ON invitations
        USING (
            tenant_id::text = current_setting('app.current_tenant_id', true)
            OR current_setting('app.is_platform_admin', true) = 'true'
        )
    """)
    
    # Enable RLS on memberships table
    op.execute("ALTER TABLE memberships ENABLE ROW LEVEL SECURITY")
    
    # Policy: Allow access if tenant_id matches session variable OR user is platform admin
    op.execute("""
        CREATE POLICY memberships_tenant_isolation ON memberships
        USING (
            tenant_id::text = current_setting('app.current_tenant_id', true)
            OR current_setting('app.is_platform_admin', true) = 'true'
        )
    """)
    
    # Note: sessions table is user-scoped, not tenant-scoped, so no RLS needed
    # Note: users and tenants are platform-level tables, accessed via specific queries


def downgrade() -> None:
    """Disable Row-Level Security."""
    
    # Drop policies
    op.execute("DROP POLICY IF EXISTS memberships_tenant_isolation ON memberships")
    op.execute("DROP POLICY IF EXISTS invitations_tenant_isolation ON invitations")
    
    # Disable RLS
    op.execute("ALTER TABLE memberships DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE invitations DISABLE ROW LEVEL SECURITY")
