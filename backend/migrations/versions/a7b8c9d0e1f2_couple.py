"""couple urunleri — couple_products (2 tasarimli cift kilif)

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "couple_products",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("store_id", UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("product_id", sa.String(length=50), nullable=False, index=True),
        sa.Column("product_title", sa.String(length=500), nullable=True),
        sa.Column("product_image_url", sa.String(length=1000), nullable=True),
        sa.Column("design_id_1", UUID(as_uuid=True), sa.ForeignKey("designs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("design_id_2", UUID(as_uuid=True), sa.ForeignKey("designs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("store_id", "product_id", name="uq_couple_store_product"),
    )


def downgrade() -> None:
    op.drop_table("couple_products")
