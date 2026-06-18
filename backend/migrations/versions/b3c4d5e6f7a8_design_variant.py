"""design variant_id (coklu varyasyon tasarimlari)

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-06-17

"""
from alembic import op
import sqlalchemy as sa

revision = "b3c4d5e6f7a8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("designs", sa.Column("variant_id", sa.String(length=50), nullable=True))
    op.add_column("designs", sa.Column("variant_title", sa.String(length=200), nullable=True))
    op.create_index("ix_designs_variant_id", "designs", ["variant_id"])


def downgrade() -> None:
    op.drop_index("ix_designs_variant_id", table_name="designs")
    op.drop_column("designs", "variant_title")
    op.drop_column("designs", "variant_id")
