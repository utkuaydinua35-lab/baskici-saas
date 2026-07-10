"""Varyant setleri + kişiye özel alanlar + couple ürünler

Revision ID: s0n1v2w3x4y5
Revises: r8l9u0v1w2x3
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "s0n1v2w3x4y5"
down_revision = "r8l9u0v1w2x3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "variant_sets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("store_id", UUID(as_uuid=True),
                  sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("items", JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("store_id", "name", name="uq_variant_set_store_name"),
    )
    op.add_column("catalog_products", sa.Column(
        "variant_set_id", UUID(as_uuid=True),
        sa.ForeignKey("variant_sets.id", ondelete="SET NULL"), nullable=True))
    op.add_column("catalog_products", sa.Column("custom_fields", JSONB(), nullable=True))
    op.add_column("catalog_products", sa.Column(
        "models_per_item", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    op.drop_column("catalog_products", "models_per_item")
    op.drop_column("catalog_products", "custom_fields")
    op.drop_column("catalog_products", "variant_set_id")
    op.drop_table("variant_sets")
