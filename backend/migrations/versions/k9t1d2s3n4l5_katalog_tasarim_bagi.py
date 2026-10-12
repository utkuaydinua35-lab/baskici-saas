"""katalog ürününe açık tasarım bağı (vitrin üretim eşleşmesi)

Vitrin (storefront) siparişlerinde line_items.product_id = catalog_products.id
(UUID) iken Design.product_id Shopify sayısal kimliğidir; ikisi hiçbir zaman
eşleşmez. Kalıp planlayıcı bu yüzden "ürün tasarıma bağlanmamış" diyordu.
Bağ artık açıkça catalog_products.design_id'de tutulur.

Revision ID: k9t1d2s3n4l5
Revises: t1a2s0p0y1l2
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "k9t1d2s3n4l5"
down_revision = "t1a2s0p0y1l2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "catalog_products",
        sa.Column("design_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_catalog_product_design", "catalog_products", "designs",
        ["design_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index(
        "ix_catalog_products_design_id", "catalog_products", ["design_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_catalog_products_design_id", table_name="catalog_products")
    op.drop_constraint("fk_catalog_product_design", "catalog_products", type_="foreignkey")
    op.drop_column("catalog_products", "design_id")
