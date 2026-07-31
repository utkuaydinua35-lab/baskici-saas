"""urun soru-cevap — product_reviews.kind + answer

Ayri tablo yerine mevcut yorum tablosu genisletildi: ayni moderasyon
akisi (bekliyor/onayli), ayni panel ekrani, ayni public uc.

Revision ID: k8f9a0b1c2d3
Revises: j7e8f9a0b1c2
Create Date: 2026-08-01
"""
import sqlalchemy as sa
from alembic import op

revision = "k8f9a0b1c2d3"
down_revision = "j7e8f9a0b1c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # kind: review (yildizli yorum) | question (soru-cevap)
    op.add_column("product_reviews", sa.Column(
        "kind", sa.String(20), nullable=False, server_default="review"))
    op.add_column("product_reviews", sa.Column("answer", sa.Text(), nullable=True))
    op.add_column("product_reviews", sa.Column(
        "answered_at", sa.DateTime(timezone=True), nullable=True))
    # Soruda puan yok — mevcut NOT NULL kisiti gevsetilir
    op.alter_column("product_reviews", "rating", nullable=True)
    op.create_index("ix_reviews_kind_status", "product_reviews", ["kind", "status"])


def downgrade() -> None:
    op.drop_index("ix_reviews_kind_status", table_name="product_reviews")
    op.alter_column("product_reviews", "rating", nullable=False)
    op.drop_column("product_reviews", "answered_at")
    op.drop_column("product_reviews", "answer")
    op.drop_column("product_reviews", "kind")
