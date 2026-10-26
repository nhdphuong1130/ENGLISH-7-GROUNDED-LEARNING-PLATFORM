"""Add OTP challenges and trusted admin devices.

Revision ID: 0012_admin_trusted_devices
Revises: 0011_practice_content_lifecycle
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_admin_trusted_devices"
down_revision = "0011_practice_content_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_trusted_devices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "admin_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("device_hash", sa.String(64), nullable=False),
        sa.Column("trusted_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("admin_id", "device_hash", name="uq_admin_trusted_device"),
    )
    op.create_index(
        "ix_admin_trusted_devices_admin_id",
        "admin_trusted_devices",
        ["admin_id"],
    )
    op.create_table(
        "admin_login_challenges",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "admin_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("device_hash", sa.String(64), nullable=False),
        sa.Column("target_phone", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_admin_login_challenges_admin_id",
        "admin_login_challenges",
        ["admin_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_admin_login_challenges_admin_id",
        table_name="admin_login_challenges",
    )
    op.drop_table("admin_login_challenges")
    op.drop_index("ix_admin_trusted_devices_admin_id", table_name="admin_trusted_devices")
    op.drop_table("admin_trusted_devices")
