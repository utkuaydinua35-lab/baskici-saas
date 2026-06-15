"""baskici print_status

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-06-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d9e0f1a2b3c4"
down_revision = "c8d9e0f1a2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("molds", sa.Column("print_status", sa.String(length=20), server_default="bekliyor", nullable=False))
    op.add_column("molds", sa.Column("print_note", sa.Text(), nullable=True))
    op.add_column("molds", sa.Column("print_analysis", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("molds", sa.Column("print_analyzed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("molds", "print_analyzed_at")
    op.drop_column("molds", "print_analysis")
    op.drop_column("molds", "print_note")
    op.drop_column("molds", "print_status")
