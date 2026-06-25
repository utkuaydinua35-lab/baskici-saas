"""tenants.ai_reply_enabled + ai_reply_model — AI destek yaniti ayarlari

Revision ID: j4d5e6f7a8b9
Revises: i3c4d5e6f7a8
Create Date: 2026-06-25

"""
from alembic import op
import sqlalchemy as sa

revision = "j4d5e6f7a8b9"
down_revision = "i3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column(
        "ai_reply_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("tenants", sa.Column(
        "ai_reply_model", sa.String(length=20), nullable=False, server_default=sa.text("'opus'")))


def downgrade() -> None:
    op.drop_column("tenants", "ai_reply_model")
    op.drop_column("tenants", "ai_reply_enabled")
