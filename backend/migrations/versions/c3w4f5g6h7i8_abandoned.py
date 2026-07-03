"""terk sepet hatirlatmasi: checkout_sessions.reminder_sent_at

Revision ID: c3w4f5g6h7i8
Revises: b2v3e4f5g6h7
Create Date: 2026-07-03

"""
from alembic import op
import sqlalchemy as sa

revision = "c3w4f5g6h7i8"
down_revision = "b2v3e4f5g6h7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("checkout_sessions", sa.Column(
        "reminder_sent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("checkout_sessions", "reminder_sent_at")
