"""musteri crm: customers tablosu + orders.customer_email index'i

Revision ID: z0t1c2d3e4f5
Revises: y9s0b1c2d3e4
Create Date: 2026-07-03

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "z0t1c2d3e4f5"
down_revision = "y9s0b1c2d3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("orders_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_spent", sa.Numeric(14, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("first_order_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_order_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "email", name="uq_customer_tenant_email"),
    )
    # Müşteri bazlı sipariş sorguları (CRM detay + agrega yeniden hesabı) için
    op.create_index("ix_orders_customer_email", "orders", ["customer_email"])


def downgrade() -> None:
    op.drop_index("ix_orders_customer_email", table_name="orders")
    op.drop_table("customers")
