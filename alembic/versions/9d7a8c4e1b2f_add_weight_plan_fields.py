"""add weight plan fields

Revision ID: 9d7a8c4e1b2f
Revises: 782180897d86
Create Date: 2026-02-21 10:30:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9d7a8c4e1b2f"
down_revision: Union[str, Sequence[str], None] = "782180897d86"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("target_weight_kg", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("weight_plan_mode", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("weight_plan_start_date", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("weight_plan_start_kg", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("weight_plan_start_kg")
        batch_op.drop_column("weight_plan_start_date")
        batch_op.drop_column("weight_plan_mode")
        batch_op.drop_column("target_weight_kg")
