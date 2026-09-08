"""designs.onizleme_path + dosya_silindi_at

Revision ID: d7a8b9c0e1f2
Revises: c6f7a8b9d0e1
"""
from alembic import op
import sqlalchemy as sa

revision = "d7a8b9c0e1f2"
down_revision = "c6f7a8b9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("designs", sa.Column("onizleme_path", sa.String(length=500), nullable=True))
    op.add_column("designs", sa.Column(
        "dosya_silindi_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_designs_dosya_silindi_at", "designs", ["dosya_silindi_at"])


def downgrade() -> None:
    op.drop_index("ix_designs_dosya_silindi_at", table_name="designs")
    op.drop_column("designs", "dosya_silindi_at")
    op.drop_column("designs", "onizleme_path")
