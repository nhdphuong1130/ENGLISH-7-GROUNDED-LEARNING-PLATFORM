"""Group Tutor exchanges into bounded, owner-scoped conversations.

Revision ID: 0009_tutor_conversations
Revises: 0008_tutor_chats
"""

from datetime import timedelta
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "0009_tutor_conversations"
down_revision = "0008_tutor_chats"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "tutor_conversations" not in tables:
        op.create_table(
            "tutor_conversations",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Uuid(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("title", sa.Unicode(160), nullable=False),
            sa.Column("language", sa.String(10), nullable=False),
            sa.Column("addressing_preference", sa.Unicode(120)),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(
            "ix_tutor_conversations_owner_updated",
            "tutor_conversations",
            ["user_id", "updated_at"],
        )

    chat_columns = {
        column["name"] for column in sa.inspect(bind).get_columns("tutor_chats")
    }
    if "conversation_id" not in chat_columns:
        op.add_column(
            "tutor_chats",
            sa.Column("conversation_id", sa.Uuid(), nullable=True),
        )
    if "sequence_number" not in chat_columns:
        op.add_column(
            "tutor_chats",
            sa.Column("sequence_number", sa.Integer(), nullable=True),
        )

    metadata = sa.MetaData()
    conversations = sa.Table(
        "tutor_conversations",
        metadata,
        sa.Column("id", sa.Uuid()),
        sa.Column("user_id", sa.Uuid()),
        sa.Column("title", sa.Unicode(160)),
        sa.Column("language", sa.String(10)),
        sa.Column("addressing_preference", sa.Unicode(120)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    chats = sa.Table(
        "tutor_chats",
        metadata,
        sa.Column("id", sa.Uuid()),
        sa.Column("user_id", sa.Uuid()),
        sa.Column("question", sa.UnicodeText()),
        sa.Column("language", sa.String(10)),
        sa.Column("conversation_id", sa.Uuid()),
        sa.Column("sequence_number", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    # FreeTDS allows only one active result set per connection. Materialize the
    # legacy rows before inserting conversations so those writes do not close
    # the cursor that is still being iterated.
    legacy_rows = bind.execute(
        sa.select(
            chats.c.id,
            chats.c.user_id,
            chats.c.question,
            chats.c.language,
            chats.c.created_at,
            chats.c.updated_at,
        ).where(chats.c.conversation_id.is_(None))
    ).mappings().all()
    for row in legacy_rows:
        conversation_id = uuid4()
        created_at = row["created_at"]
        updated_at = row["updated_at"] or created_at
        title = " ".join((row["question"] or "Tutor conversation").split())
        bind.execute(
            conversations.insert().values(
                id=conversation_id,
                user_id=row["user_id"],
                title=title[:160] or "Tutor conversation",
                language=row["language"],
                addressing_preference=None,
                expires_at=updated_at + timedelta(days=90),
                created_at=created_at,
                updated_at=updated_at,
            )
        )
        bind.execute(
            chats.update()
            .where(chats.c.id == row["id"])
            .values(conversation_id=conversation_id, sequence_number=1)
        )

    op.alter_column(
        "tutor_chats", "conversation_id", existing_type=sa.Uuid(), nullable=False
    )
    op.alter_column(
        "tutor_chats", "sequence_number", existing_type=sa.Integer(), nullable=False
    )
    op.create_foreign_key(
        "fk_tutor_chats_conversation_id",
        "tutor_chats",
        "tutor_conversations",
        ["conversation_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_tutor_chats_conversation_sequence",
        "tutor_chats",
        ["conversation_id", "sequence_number"],
    )
    op.create_unique_constraint(
        "uq_tutor_chats_conversation_sequence",
        "tutor_chats",
        ["conversation_id", "sequence_number"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_tutor_chats_conversation_sequence",
        "tutor_chats",
        type_="unique",
    )
    op.drop_index(
        "ix_tutor_chats_conversation_sequence", table_name="tutor_chats"
    )
    op.drop_constraint(
        "fk_tutor_chats_conversation_id", "tutor_chats", type_="foreignkey"
    )
    op.drop_column("tutor_chats", "sequence_number")
    op.drop_column("tutor_chats", "conversation_id")
    op.drop_index(
        "ix_tutor_conversations_owner_updated",
        table_name="tutor_conversations",
    )
    op.drop_table("tutor_conversations")
