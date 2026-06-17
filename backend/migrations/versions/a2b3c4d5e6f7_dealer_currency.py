"""dealer currency (sabit para birimi TRY/USD)

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-06-17

"""
from alembic import op
import sqlalchemy as sa

revision = "a2b3c4d5e6f7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("dealers", sa.Column("currency", sa.String(length=3), server_default="TRY", nullable=False))


def downgrade() -> None:
    op.drop_column("dealers", "currency")
