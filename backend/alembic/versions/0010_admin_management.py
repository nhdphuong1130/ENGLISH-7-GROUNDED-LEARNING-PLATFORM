"""Add admin account lifecycle, revisions, and audit context.

Revision ID: 0010_admin_management
Revises: 0009_tutor_conversations
"""

import sqlalchemy as sa
from alembic import op

revision = "0010_admin_management"
down_revision = "0009_tutor_conversations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_archived_at", "users", ["archived_at"])

    op.add_column("audit_events", sa.Column("request_id", sa.String(100)))
    op.add_column("audit_events", sa.Column("ip_address", sa.String(64)))
    op.add_column("audit_events", sa.Column("platform", sa.String(100)))
    op.add_column("audit_events", sa.Column("before_data", sa.JSON()))
    op.add_column("audit_events", sa.Column("after_data", sa.JSON()))
    op.add_column(
        "audit_events",
        sa.Column(
            "succeeded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.create_index("ix_audit_events_request_id", "audit_events", ["request_id"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])

    op.create_table(
        "content_revisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column(
            "actor_id",
            sa.Uuid(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "entity_type",
            "entity_id",
            "version",
            name="uq_content_revision_entity_version",
        ),
    )
    op.create_index(
        "ix_content_revision_entity",
        "content_revisions",
        ["entity_type", "entity_id", "version"],
    )


def downgrade() -> None:
    op.drop_index("ix_content_revision_entity", table_name="content_revisions")
    op.drop_table("content_revisions")
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_request_id", table_name="audit_events")
    op.drop_column("audit_events", "succeeded")
    op.drop_column("audit_events", "after_data")
    op.drop_column("audit_events", "before_data")
    op.drop_column("audit_events", "platform")
    op.drop_column("audit_events", "ip_address")
    op.drop_column("audit_events", "request_id")
    op.drop_index("ix_users_archived_at", table_name="users")
    op.drop_column("users", "archived_at")
