"""dealer usd balance + tx currency

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
Create Date: 2026-06-15

"""
from alembic import op
import sqlalchemy as sa

revision = "e0f1a2b3c4d5"
down_revision = "d9e0f1a2b3c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("dealers", sa.Column("balance_usd", sa.Numeric(12, 2), server_default="0", nullable=False))
    op.add_column("dealer_transactions", sa.Column("currency", sa.String(length=3), server_default="TRY", nullable=False))


def downgrade() -> None:
    op.drop_column("dealer_transactions", "currency")
    op.drop_column("dealers", "balance_usd")
