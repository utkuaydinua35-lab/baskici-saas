"""urun yorumlari: product_reviews tablosu

Revision ID: f6z7i8j9k0l1
Revises: e5y6h7i8j9k0
Create Date: 2026-07-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "f6z7i8j9k0l1"
down_revision = "e5y6h7i8j9k0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_reviews",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("product_id", UUID(as_uuid=True),
                  sa.ForeignKey("catalog_products.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("checkout_session_id", UUID(as_uuid=True),
                  sa.ForeignKey("checkout_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("author_name", sa.String(60), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), server_default=sa.text("'pending'"),
                  nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("product_id", "checkout_session_id", name="uq_review_product_session"),
    )


def downgrade() -> None:
    op.drop_table("product_reviews")
