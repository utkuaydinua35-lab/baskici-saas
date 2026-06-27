"""marketing_subscribers: pazarlama e-posta abonesi (KVKK uyumlu)

Revision ID: o9i0d1e2f3a4
Revises: n8h9c0d1e2f3
Create Date: 2026-06-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "o9i0d1e2f3a4"
down_revision = "n8h9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketing_subscribers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("source", sa.String(30), nullable=True),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_ip", sa.String(60), nullable=True),
        sa.Column("consent_text", sa.Text(), nullable=True),
        sa.Column("confirm_token", sa.String(64), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unsubscribe_token", sa.String(64), nullable=True),
        sa.Column("unsubscribed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "email", name="uq_mkt_sub_tenant_email"),
    )
    op.create_index("ix_marketing_subscribers_tenant_id", "marketing_subscribers", ["tenant_id"])
    op.create_index("ix_marketing_subscribers_email", "marketing_subscribers", ["email"])
    op.create_index("ix_marketing_subscribers_status", "marketing_subscribers", ["status"])
    op.create_index("ix_marketing_subscribers_confirm_token", "marketing_subscribers", ["confirm_token"])
    op.create_index("ix_marketing_subscribers_unsubscribe_token", "marketing_subscribers", ["unsubscribe_token"])


def downgrade() -> None:
    op.drop_table("marketing_subscribers")
