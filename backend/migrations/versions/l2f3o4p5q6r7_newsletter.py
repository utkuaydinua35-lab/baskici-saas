"""Bülten aboneliği: customers.accepts_marketing + marketing_opted_at

Revision ID: l2f3o4p5q6r7
Revises: k1e2n3o4p5q6
Create Date: 2026-07-09
"""
from alembic import op
import sqlalchemy as sa

revision = "l2f3o4p5q6r7"
down_revision = "k1e2n3o4p5q6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column("accepts_marketing", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "customers",
        sa.Column("marketing_opted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("customers", "marketing_opted_at")
    op.drop_column("customers", "accepts_marketing")
