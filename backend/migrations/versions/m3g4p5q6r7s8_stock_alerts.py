"""Gelince haber ver: stock_alerts

Revision ID: m3g4p5q6r7s8
Revises: l2f3o4p5q6r7
Create Date: 2026-07-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "m3g4p5q6r7s8"
down_revision = "l2f3o4p5q6r7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stock_alerts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("store_id", UUID(as_uuid=True),
                  sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("variant_id", UUID(as_uuid=True),
                  sa.ForeignKey("catalog_variants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("variant_id", "email", name="uq_stock_alert_variant_email"),
    )


def downgrade() -> None:
    op.drop_table("stock_alerts")
