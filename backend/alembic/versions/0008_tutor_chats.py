"""Add tutor_chats table for persisting AI tutor conversations.

Revision ID: 0008_tutor_chats
Revises: 0007_learning
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_tutor_chats"
down_revision = "0007_learning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "tutor_chats" not in inspector.get_table_names():
        op.create_table(
            "tutor_chats",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("question", sa.UnicodeText(), nullable=False),
            sa.Column("answer", sa.UnicodeText(), nullable=False),
            sa.Column("language", sa.String(10), nullable=False),
            sa.Column("upload_id", sa.Uuid(), sa.ForeignKey("student_image_uploads.id"), nullable=True),
            sa.Column("citations", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "tutor_chats" in inspector.get_table_names():
        op.drop_table("tutor_chats")
