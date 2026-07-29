"""line_items.is_hazir_2 — çift kılıfın 2. yarısı için ayrı 'hazır' işareti

Revision ID: e2z3a4b5c6d7
Revises: d1y2z3a4b5c6
Create Date: 2026-07-29
"""
from alembic import op
import sqlalchemy as sa

revision = "e2z3a4b5c6d7"
down_revision = "d1y2z3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "line_items",
        sa.Column("is_hazir_2", sa.Boolean(),
                  server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("line_items", "is_hazir_2")
