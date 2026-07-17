"""discount_codes.promo_message — kampanya basina duzenlenebilir vitrin mesaji

Revision ID: y6t7u8v9w0x1
Revises: x5s6t7u8v9w0
Create Date: 2026-07-18
"""
import sqlalchemy as sa
from alembic import op

revision = "y6t7u8v9w0x1"
down_revision = "x5s6t7u8v9w0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "discount_codes",
        sa.Column("promo_message", sa.String(200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("discount_codes", "promo_message")
