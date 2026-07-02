"""vitrin (storefront): catalog_products/variants/images + checkout_sessions + siparis no sequence

Revision ID: x8r9a0b1c2d3
Revises: w7q8f9a0b1c2
Create Date: 2026-07-02

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "x8r9a0b1c2d3"
down_revision = "w7q8f9a0b1c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalog_products",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("store_id", UUID(as_uuid=True),
                  sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), server_default=sa.text("'draft'"), nullable=False, index=True),
        sa.Column("seo_title", sa.String(200), nullable=True),
        sa.Column("seo_description", sa.String(400), nullable=True),
        sa.Column("base_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("compare_at_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(3), server_default=sa.text("'TRY'"), nullable=False),
        sa.Column("tags", sa.String(500), nullable=True),
        sa.Column("position", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("store_id", "slug", name="uq_catalog_product_store_slug"),
    )

    op.create_table(
        "catalog_variants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("product_id", UUID(as_uuid=True),
                  sa.ForeignKey("catalog_products.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("model_key", sa.String(60), nullable=False),
        sa.Column("model_display", sa.String(120), nullable=False),
        sa.Column("variation", sa.String(30), nullable=True),
        sa.Column("sku", sa.String(100), nullable=True),
        sa.Column("price_override", sa.Numeric(12, 2), nullable=True),
        sa.Column("quantity", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("track_stock", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("stock_item_id", UUID(as_uuid=True),
                  sa.ForeignKey("stock_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("position", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("product_id", "model_key", "variation", name="uq_catalog_variant_model_var"),
    )

    op.create_table(
        "catalog_images",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("product_id", UUID(as_uuid=True),
                  sa.ForeignKey("catalog_products.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("variant_id", UUID(as_uuid=True),
                  sa.ForeignKey("catalog_variants.id", ondelete="SET NULL"), nullable=True),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("alt", sa.String(200), nullable=True),
        sa.Column("position", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "checkout_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("store_id", UUID(as_uuid=True),
                  sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("token", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("lookup_token", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("status", sa.String(20), server_default=sa.text("'pending'"), nullable=False, index=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_ref", sa.String(200), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("shipping_amount", sa.Numeric(12, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("currency", sa.String(3), server_default=sa.text("'TRY'"), nullable=False),
        sa.Column("cart_snapshot", JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("customer", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("kvkk_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("order_id", UUID(as_uuid=True),
                  sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("callback_raw", JSONB(), nullable=True),
        sa.Column("client_ip", sa.String(60), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
    )

    # İnsan-dostu vitrin sipariş numarası (tenant'lar arası paylaşımlı, 1001'den başlar)
    op.execute("CREATE SEQUENCE IF NOT EXISTS storefront_order_number_seq START 1001")


def downgrade() -> None:
    op.execute("DROP SEQUENCE IF EXISTS storefront_order_number_seq")
    op.drop_table("checkout_sessions")
    op.drop_table("catalog_images")
    op.drop_table("catalog_variants")
    op.drop_table("catalog_products")
