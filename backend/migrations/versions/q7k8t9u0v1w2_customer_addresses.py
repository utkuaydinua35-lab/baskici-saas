"""Müşteri adres defteri: customers.addresses

Revision ID: q7k8t9u0v1w2
Revises: p6j7s8t9u0v1
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "q7k8t9u0v1w2"
down_revision = "p6j7s8t9u0v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("addresses", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("customers", "addresses")
