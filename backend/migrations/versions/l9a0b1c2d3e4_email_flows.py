"""e-posta akislari — customers.welcome_sent_at + orders.review_invite_sent_at

Idempotent isaretler: her musteriye 1 hos geldin, her siparise 1 yorum daveti.

Revision ID: l9a0b1c2d3e4
Revises: k8f9a0b1c2d3
Create Date: 2026-08-01
"""
import sqlalchemy as sa
from alembic import op

revision = "l9a0b1c2d3e4"
down_revision = "k8f9a0b1c2d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("customers", sa.Column(
        "welcome_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column(
        "review_invite_sent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "review_invite_sent_at")
    op.drop_column("customers", "welcome_sent_at")
