"""aktivite gunlugu — activity_log tablosu

Katalog/ayar tarafinda "kim neyi degistirdi" kaydi. Siparis asamalari
OrderStatusHistory'de kalir.

Revision ID: q4f5a6b7c8d9
Revises: p3e4f5a6b7c8
Create Date: 2026-08-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "q4f5a6b7c8d9"
down_revision = "p3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activity_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("store_id", UUID(as_uuid=True),
                  sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=True),
        sa.Column("user_email", sa.String(200), nullable=True),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=True),
        sa.Column("entity_id", sa.String(60), nullable=True),
        sa.Column("entity_label", sa.String(300), nullable=True),
        sa.Column("detail", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_activity_log_tenant_id", "activity_log", ["tenant_id"])
    op.create_index("ix_activity_log_store_id", "activity_log", ["store_id"])
    op.create_index("ix_activity_log_action", "activity_log", ["action"])
    op.create_index("ix_activity_log_created_at", "activity_log", ["created_at"])


def downgrade() -> None:
    op.drop_table("activity_log")
