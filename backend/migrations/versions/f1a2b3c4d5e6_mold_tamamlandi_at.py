"""mold tamamlandi_at

Revision ID: f1a2b3c4d5e6
Revises: e0f1a2b3c4d5
Create Date: 2026-06-15

"""
from alembic import op
import sqlalchemy as sa

revision = "f1a2b3c4d5e6"
down_revision = "e0f1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("molds", sa.Column("tamamlandi_at", sa.DateTime(timezone=True), nullable=True))
    # Mevcut tamamlanmis kaliplari isaretle (updated_at'i baz al)
    op.execute("UPDATE molds SET tamamlandi_at = updated_at WHERE current_stage = 5 AND tamamlandi_at IS NULL")


def downgrade() -> None:
    op.drop_column("molds", "tamamlandi_at")
