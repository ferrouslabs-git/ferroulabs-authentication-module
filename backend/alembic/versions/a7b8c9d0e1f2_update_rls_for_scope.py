"""update rls for scope

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-03-20 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Replace legacy tenant-based RLS policies with scope-based policies.

    New policies filter on (scope_type, scope_id) for memberships,
    (target_scope_type, target_scope_id) for invitations,
    and account_id for spaces.

    Super-admin bypass uses app.is_super_admin.
    """

    # ── Memberships: drop old policy, create scope-based ────────────
    op.execute(
        "DROP POLICY IF EXISTS memberships_tenant_isolation ON memberships"
    )
    op.execute("""
        CREATE POLICY memberships_scope_isolation ON memberships
        USING (
            (
                scope_type = current_setting('app.current_scope_type', true)
                AND scope_id::text = current_setting('app.current_scope_id', true)
            )
            OR current_setting('app.is_super_admin', true) = 'true'
            OR current_setting('app.is_platform_admin', true) = 'true'
        )
    """)

    # ── Invitations: drop old policy, create scope-based ────────────
    op.execute(
        "DROP POLICY IF EXISTS invitations_tenant_isolation ON invitations"
    )
    op.execute("""
        CREATE POLICY invitations_scope_isolation ON invitations
        USING (
            (
                target_scope_type = current_setting('app.current_scope_type', true)
                AND target_scope_id::text = current_setting('app.current_scope_id', true)
            )
            OR tenant_id::text = current_setting('app.current_tenant_id', true)
            OR current_setting('app.is_super_admin', true) = 'true'
            OR current_setting('app.is_platform_admin', true) = 'true'
        )
    """)

    # ── Spaces: new table, enable RLS + policy ──────────────────────
    op.execute("ALTER TABLE spaces ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE spaces FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY spaces_account_isolation ON spaces
        USING (
            account_id::text = current_setting('app.current_scope_id', true)
            OR current_setting('app.is_super_admin', true) = 'true'
            OR current_setting('app.is_platform_admin', true) = 'true'
        )
    """)


def downgrade() -> None:
    """Revert to legacy tenant-based RLS policies."""

    # ── Spaces: drop policy + disable RLS ───────────────────────────
    op.execute("DROP POLICY IF EXISTS spaces_account_isolation ON spaces")
    op.execute("ALTER TABLE spaces NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE spaces DISABLE ROW LEVEL SECURITY")

    # ── Invitations: revert to tenant-based policy ──────────────────
    op.execute(
        "DROP POLICY IF EXISTS invitations_scope_isolation ON invitations"
    )
    op.execute("""
        CREATE POLICY invitations_tenant_isolation ON invitations
        USING (
            tenant_id::text = current_setting('app.current_tenant_id', true)
            OR current_setting('app.is_platform_admin', true) = 'true'
        )
    """)

    # ── Memberships: revert to tenant-based policy ──────────────────
    op.execute(
        "DROP POLICY IF EXISTS memberships_scope_isolation ON memberships"
    )
    op.execute("""
        CREATE POLICY memberships_tenant_isolation ON memberships
        USING (
            tenant_id::text = current_setting('app.current_tenant_id', true)
            OR current_setting('app.is_platform_admin', true) = 'true'
        )
    """)
