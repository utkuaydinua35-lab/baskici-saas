"""instagram dm otomasyon kaydi

Revision ID: b9w0x1y2z3a4
Revises: a8v9w0x1y2z3
Create Date: 2026-07-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "b9w0x1y2z3a4"
down_revision = "a8v9w0x1y2z3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "instagram_dms",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("store_id", UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sender_id", sa.String(length=64), nullable=False),
        sa.Column("incoming", sa.Text(), nullable=True),
        sa.Column("reply", sa.Text(), nullable=True),
        sa.Column("rule", sa.String(length=40), nullable=True),
        sa.Column("sent_ok", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_instagram_dms_tenant_id", "instagram_dms", ["tenant_id"])
    op.create_index("ix_instagram_dms_store_id", "instagram_dms", ["store_id"])
    op.create_index("ix_instagram_dms_sender_id", "instagram_dms", ["sender_id"])
    op.create_index("ix_instagram_dms_rule", "instagram_dms", ["rule"])
    op.create_index("ix_instagram_dms_created_at", "instagram_dms", ["created_at"])


def downgrade():
    op.drop_table("instagram_dms")
