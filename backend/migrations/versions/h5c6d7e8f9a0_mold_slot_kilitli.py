"""molds.slot_kilitli — slot pozisyonlarini kilitle (silince kalanlar kaymasin)

Revision ID: h5c6d7e8f9a0
Revises: e2z3a4b5c6d7
Create Date: 2026-07-29
"""
from alembic import op
import sqlalchemy as sa

revision = "h5c6d7e8f9a0"
down_revision = "e2z3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "molds",
        sa.Column("slot_kilitli", sa.Boolean(),
                  server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("molds", "slot_kilitli")
