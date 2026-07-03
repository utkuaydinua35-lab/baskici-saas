"""vitrin koleksiyonlari: catalog_collections + urun M2M

Revision ID: b2v3e4f5g6h7
Revises: a1u2d3e4f5g6
Create Date: 2026-07-03

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "b2v3e4f5g6h7"
down_revision = "a1u2d3e4f5g6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalog_collections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("store_id", UUID(as_uuid=True),
                  sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("image_path", sa.String(500), nullable=True),
        sa.Column("position", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("store_id", "slug", name="uq_catalog_collection_store_slug"),
    )
    op.create_table(
        "catalog_product_collections",
        sa.Column("product_id", UUID(as_uuid=True),
                  sa.ForeignKey("catalog_products.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("collection_id", UUID(as_uuid=True),
                  sa.ForeignKey("catalog_collections.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("catalog_product_collections")
    op.drop_table("catalog_collections")
