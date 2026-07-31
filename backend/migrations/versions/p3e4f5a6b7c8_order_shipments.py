"""kismi kargolama — order_shipments tablosu

Bir siparisin parca parca gonderilmesi: hangi kalemden kac adet, hangi
takip numarasiyla. Order.kargo_info degismeden kalir (Basit Kargo/webhook).

Revision ID: p3e4f5a6b7c8
Revises: o2d3e4f5a6b7
Create Date: 2026-08-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "p3e4f5a6b7c8"
down_revision = "o2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "order_shipments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", UUID(as_uuid=True),
                  sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("takip_no", sa.String(100), nullable=True),
        sa.Column("kargo_firma", sa.String(100), nullable=True),
        sa.Column("takip_url", sa.String(500), nullable=True),
        sa.Column("items", JSONB(), nullable=True),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_by", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_order_shipments_tenant_id", "order_shipments", ["tenant_id"])
    op.create_index("ix_order_shipments_order_id", "order_shipments", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_order_shipments_order_id", table_name="order_shipments")
    op.drop_index("ix_order_shipments_tenant_id", table_name="order_shipments")
    op.drop_table("order_shipments")
