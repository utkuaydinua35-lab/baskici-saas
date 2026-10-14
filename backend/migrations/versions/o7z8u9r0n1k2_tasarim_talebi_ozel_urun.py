"""design_requests.product_id + bildirildi_at — talebe özel (linkle görünen) ürün

Revision ID: o7z8u9r0n1k2
Revises: f0r1m2a3t4s5
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "o7z8u9r0n1k2"
down_revision = "f0r1m2a3t4s5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("design_requests", sa.Column(
        "product_id", UUID(as_uuid=True),
        sa.ForeignKey("catalog_products.id", ondelete="SET NULL"), nullable=True))
    op.add_column("design_requests", sa.Column(
        "bildirildi_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("design_requests", "bildirildi_at")
    op.drop_column("design_requests", "product_id")
