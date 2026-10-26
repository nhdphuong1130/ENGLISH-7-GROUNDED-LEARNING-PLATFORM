"""Add lifecycle flags for administered practice content.

Revision ID: 0011_practice_content_lifecycle
Revises: 0010_admin_management
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_practice_content_lifecycle"
down_revision = "0010_admin_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("flashcard_decks", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("flashcards", sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    op.drop_column("flashcards", "is_published")
    op.drop_column("flashcard_decks", "is_active")
