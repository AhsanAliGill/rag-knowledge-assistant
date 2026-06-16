"""conversation indexes, cascade delete, utc timestamps

Revision ID: 27a31a8e5963
Revises: c76c2e9bf439
Create Date: 2026-06-16

Changes:
  - Replace single-column index on rag_conversations.user_id with a composite
    covering index (user_id, updated_at DESC) so list_conversations can do an
    index-only scan and skip the sort step entirely.
  - Replace single-column index on rag_conversation_messages.conversation_id
    with a composite index (conversation_id, created_at ASC) so history loads
    and get_conversation skip the sort step.
  - Add ON DELETE CASCADE to the messages FK so deleting a conversation
    removes its messages in a single DB round-trip.
  - Convert created_at / updated_at on both tables to TIMESTAMPTZ (timezone-aware)
    to match the users table and avoid naive-datetime bugs.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "27a31a8e5963"
down_revision: Union[str, None] = "c76c2e9bf439"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. rag_conversations: composite index (user_id, updated_at DESC) ──────
    op.drop_index("ix_rag_conversations_user_id", table_name="rag_conversations")
    op.create_index(
        "ix_rag_conversations_user_updated",
        "rag_conversations",
        ["user_id", sa.text("updated_at DESC")],
        postgresql_using="btree",
    )

    # ── 2. rag_conversation_messages: composite index (conv_id, created_at ASC)
    op.drop_index(
        "ix_rag_conversation_messages_conversation_id",
        table_name="rag_conversation_messages",
    )
    op.create_index(
        "ix_rag_conv_messages_conv_created",
        "rag_conversation_messages",
        ["conversation_id", sa.text("created_at ASC")],
        postgresql_using="btree",
    )

    # ── 3. Add ON DELETE CASCADE to the FK ───────────────────────────────────
    # PostgreSQL auto-names the FK as <table>_<col>_fkey
    op.drop_constraint(
        "rag_conversation_messages_conversation_id_fkey",
        "rag_conversation_messages",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_rag_conv_messages_conversation_id",
        "rag_conversation_messages",
        "rag_conversations",
        ["conversation_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # ── 4. Convert timestamps to TIMESTAMPTZ ─────────────────────────────────
    for table, col in [
        ("rag_conversations", "created_at"),
        ("rag_conversations", "updated_at"),
        ("rag_conversation_messages", "created_at"),
    ]:
        op.alter_column(
            table,
            col,
            existing_type=postgresql.TIMESTAMP(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=f"{col} AT TIME ZONE 'UTC'",
        )


def downgrade() -> None:
    # Reverse timestamp conversions
    for table, col in [
        ("rag_conversation_messages", "created_at"),
        ("rag_conversations", "updated_at"),
        ("rag_conversations", "created_at"),
    ]:
        op.alter_column(
            table,
            col,
            existing_type=sa.DateTime(timezone=True),
            type_=postgresql.TIMESTAMP(),
            existing_nullable=False,
        )

    # Restore original FK (no CASCADE)
    op.drop_constraint(
        "fk_rag_conv_messages_conversation_id",
        "rag_conversation_messages",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "rag_conversation_messages_conversation_id_fkey",
        "rag_conversation_messages",
        "rag_conversations",
        ["conversation_id"],
        ["id"],
    )

    # Restore original single-column indexes
    op.drop_index("ix_rag_conv_messages_conv_created", table_name="rag_conversation_messages")
    op.create_index(
        "ix_rag_conversation_messages_conversation_id",
        "rag_conversation_messages",
        ["conversation_id"],
    )

    op.drop_index("ix_rag_conversations_user_updated", table_name="rag_conversations")
    op.create_index(
        "ix_rag_conversations_user_id",
        "rag_conversations",
        ["user_id"],
    )
