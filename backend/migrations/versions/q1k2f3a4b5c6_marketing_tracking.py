"""marketing tracking: kampanya open/click sayaclari + marketing_sends

Revision ID: q1k2f3a4b5c6
Revises: p0j1e2f3a4b5
Create Date: 2026-06-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "q1k2f3a4b5c6"
down_revision = "p0j1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("marketing_campaigns",
                  sa.Column("open_count", sa.Integer(), server_default=sa.text("0")))
    op.add_column("marketing_campaigns",
                  sa.Column("click_count", sa.Integer(), server_default=sa.text("0")))

    op.create_table(
        "marketing_sends",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_id", UUID(as_uuid=True),
                  sa.ForeignKey("marketing_campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscriber_id", UUID(as_uuid=True),
                  sa.ForeignKey("marketing_subscribers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), server_default=sa.text("'sent'")),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("open_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("clicked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("click_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_marketing_sends_campaign_id", "marketing_sends", ["campaign_id"])


def downgrade() -> None:
    op.drop_table("marketing_sends")
    op.drop_column("marketing_campaigns", "click_count")
    op.drop_column("marketing_campaigns", "open_count")
