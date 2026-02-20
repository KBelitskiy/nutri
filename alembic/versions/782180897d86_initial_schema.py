"""initial schema

Revision ID: 782180897d86
Revises:
Create Date: 2026-02-21 00:52:45.390815

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "782180897d86"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("telegram_id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("gender", sa.String(16), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("height_cm", sa.Float(), nullable=False),
        sa.Column("weight_start_kg", sa.Float(), nullable=False),
        sa.Column("activity_level", sa.String(32), nullable=False),
        sa.Column("goal", sa.String(16), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=True),
        sa.Column("daily_calories_target", sa.Float(), nullable=False),
        sa.Column("daily_protein_target", sa.Float(), nullable=False),
        sa.Column("daily_fat_target", sa.Float(), nullable=False),
        sa.Column("daily_carbs_target", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "weight_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "telegram_id",
            sa.Integer(),
            sa.ForeignKey("users.telegram_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("weight_kg", sa.Float(), nullable=False),
        sa.Column(
            "logged_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "meal_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "telegram_id",
            sa.Integer(),
            sa.ForeignKey("users.telegram_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("calories", sa.Float(), nullable=False),
        sa.Column("protein_g", sa.Float(), nullable=False),
        sa.Column("fat_g", sa.Float(), nullable=False),
        sa.Column("carbs_g", sa.Float(), nullable=False),
        sa.Column("photo_file_id", sa.String(255), nullable=True),
        sa.Column("meal_type", sa.String(32), nullable=False, server_default="snack"),
        sa.Column(
            "logged_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "group_chats",
        sa.Column("chat_id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "group_chat_members",
        sa.Column(
            "chat_id",
            sa.Integer(),
            sa.ForeignKey("group_chats.chat_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("telegram_id", sa.Integer(), primary_key=True),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("group_chat_members")
    op.drop_table("group_chats")
    op.drop_table("meal_logs")
    op.drop_table("weight_logs")
    op.drop_table("users")
