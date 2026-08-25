"""Beyaz altlık — molds.beyaz_slotlar + mold_templates.beyaz_k

Revision ID: a4d5e6f7b8c9
Revises: z3c4d5e6f7a8
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a4d5e6f7b8c9"
down_revision = "z3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("molds", sa.Column(
        "beyaz_slotlar", postgresql.JSONB(), nullable=False,
        server_default=sa.text("'[]'::jsonb")))
    op.add_column("mold_templates", sa.Column(
        "beyaz_k", sa.Float(), nullable=False, server_default=sa.text("0.05")))


def downgrade() -> None:
    op.drop_column("mold_templates", "beyaz_k")
    op.drop_column("molds", "beyaz_slotlar")
