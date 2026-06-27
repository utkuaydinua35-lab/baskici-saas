"""order kargo_info: Basit Kargo gonderi referansi (JSONB)

Revision ID: n8h9c0d1e2f3
Revises: m7g8b9c0d1e2
Create Date: 2026-06-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "n8h9c0d1e2f3"
down_revision = "m7g8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("kargo_info", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "kargo_info")
