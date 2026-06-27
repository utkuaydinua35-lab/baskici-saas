"""marketing_campaigns: pazarlama kampanyasi (toplu e-posta)

Revision ID: p0j1e2f3a4b5
Revises: o9i0d1e2f3a4
Create Date: 2026-06-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "p0j1e2f3a4b5"
down_revision = "o9i0d1e2f3a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketing_campaigns",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject", sa.String(300), nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("button_label", sa.String(80), nullable=True),
        sa.Column("button_url", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("recipient_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("sent_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("fail_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("created_by", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_marketing_campaigns_tenant_id", "marketing_campaigns", ["tenant_id"])
    op.create_index("ix_marketing_campaigns_status", "marketing_campaigns", ["status"])


def downgrade() -> None:
    op.drop_table("marketing_campaigns")
