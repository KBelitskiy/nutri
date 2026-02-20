"""add tracking and engagement tables

Revision ID: b3a1f5e9c2d7
Revises: 9d7a8c4e1b2f
Create Date: 2026-02-21 14:20:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3a1f5e9c2d7"
down_revision: Union[str, Sequence[str], None] = "9d7a8c4e1b2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("daily_water_target_ml", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("meal_reminder_times", sa.String(length=64), nullable=True, server_default="9,13,19")
        )

    op.create_table(
        "water_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "telegram_id",
            sa.Integer(),
            sa.ForeignKey("users.telegram_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount_ml", sa.Integer(), nullable=False),
        sa.Column(
            "logged_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "meal_templates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "telegram_id",
            sa.Integer(),
            sa.ForeignKey("users.telegram_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("calories", sa.Float(), nullable=False),
        sa.Column("protein_g", sa.Float(), nullable=False),
        sa.Column("fat_g", sa.Float(), nullable=False),
        sa.Column("carbs_g", sa.Float(), nullable=False),
        sa.Column("meal_type", sa.String(length=32), nullable=False, server_default="snack"),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "telegram_id",
            sa.Integer(),
            sa.ForeignKey("users.telegram_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "daily_checkins",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "telegram_id",
            sa.Integer(),
            sa.ForeignKey("users.telegram_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("checkin_date", sa.Date(), nullable=False),
        sa.Column("calories_ok", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("protein_ok", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("logged_meals", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_daily_checkins_checkin_date", "daily_checkins", ["checkin_date"])

    op.create_table(
        "achievements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "telegram_id",
            sa.Integer(),
            sa.ForeignKey("users.telegram_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("badge_key", sa.String(length=64), nullable=False),
        sa.Column(
            "earned_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("achievements")
    op.drop_index("ix_daily_checkins_checkin_date", table_name="daily_checkins")
    op.drop_table("daily_checkins")
    op.drop_table("conversation_messages")
    op.drop_table("meal_templates")
    op.drop_table("water_logs")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("meal_reminder_times")
        batch_op.drop_column("daily_water_target_ml")
