"""Add audit_events table for durable security audit logging.

Revision ID: 9f2e1c7a4b3d
Revises: 6c5d7e4f8a2b
Create Date: 2026-03-17 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "9f2e1c7a4b3d"
down_revision: Union[str, Sequence[str], None] = "6c5d7e4f8a2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=100), nullable=True),
        sa.Column("target_id", sa.String(length=255), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_action", "audit_events", ["action"], unique=False)
    op.create_index("ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"], unique=False)
    op.create_index("ix_audit_events_tenant_id", "audit_events", ["tenant_id"], unique=False)
    op.create_index("ix_audit_events_timestamp", "audit_events", ["timestamp"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_events_timestamp", table_name="audit_events")
    op.drop_index("ix_audit_events_tenant_id", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_user_id", table_name="audit_events")
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_table("audit_events")
