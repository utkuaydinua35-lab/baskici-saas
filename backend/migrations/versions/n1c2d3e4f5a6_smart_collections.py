"""akilli koleksiyonlar — catalog_collections.is_smart + rules + rules_match

Kural bazli otomatik uyelik. Uyelik ayni M2M tablosunda maddilesir, boylece
vitrin/filtre/kupon/feed tarafi degismeden calisir.

Revision ID: n1c2d3e4f5a6
Revises: m0b1c2d3e4f5
Create Date: 2026-08-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "n1c2d3e4f5a6"
down_revision = "m0b1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("catalog_collections", sa.Column(
        "is_smart", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("catalog_collections", sa.Column("rules", JSONB(), nullable=True))
    op.add_column("catalog_collections", sa.Column(
        "rules_match", sa.String(length=4), nullable=False, server_default=sa.text("'all'")))


def downgrade() -> None:
    op.drop_column("catalog_collections", "rules_match")
    op.drop_column("catalog_collections", "rules")
    op.drop_column("catalog_collections", "is_smart")
