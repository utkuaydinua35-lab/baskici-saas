"""paket3 — destek inbox (support_threads, support_messages)

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "support_threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("store_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("stores.id", ondelete="SET NULL"), nullable=True),
        sa.Column("shopify_order_id", sa.String(length=50), nullable=False),
        sa.Column("order_number", sa.String(length=50), nullable=True),
        sa.Column("customer_email", sa.String(length=200), nullable=True),
        sa.Column("customer_name", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="acik"),
        sa.Column("unread_admin", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_customer_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("shopify_order_id", name="uq_support_thread_order"),
    )
    op.create_index("ix_support_threads_tenant_id", "support_threads", ["tenant_id"])
    op.create_index("ix_support_threads_order_number", "support_threads", ["order_number"])
    op.create_index("ix_support_threads_status", "support_threads", ["status"])
    op.create_index("ix_support_threads_shopify_order_id", "support_threads", ["shopify_order_id"])
    op.create_index("ix_support_threads_last_message_at", "support_threads", ["last_message_at"])

    op.create_table(
        "support_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("support_threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender", sa.String(length=10), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_read_by_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_support_messages_thread_id", "support_messages", ["thread_id"])


def downgrade() -> None:
    op.drop_index("ix_support_messages_thread_id", table_name="support_messages")
    op.drop_table("support_messages")
    for ix in ["ix_support_threads_last_message_at", "ix_support_threads_shopify_order_id",
               "ix_support_threads_status", "ix_support_threads_order_number", "ix_support_threads_tenant_id"]:
        op.drop_index(ix, table_name="support_threads")
    op.drop_table("support_threads")
