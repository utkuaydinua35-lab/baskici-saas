"""faz2: line_item kilif_varyasyon(_2) + phone_models.mockup_variants

Revision ID: v6p7e8f9a0b1
Revises: u5o6d7e8f9a0
Create Date: 2026-06-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "v6p7e8f9a0b1"
down_revision = "u5o6d7e8f9a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Kişiye özel kalemin kılıf rengi/varyasyonu (SİYAH/BEYAZ/ŞEFFAF/PARLAK/MAGSAFE)
    op.add_column("line_items", sa.Column("kilif_varyasyon", sa.String(20), nullable=True))
    op.add_column("line_items", sa.Column("kilif_varyasyon_2", sa.String(20), nullable=True))
    # Telefon modeli: varyasyon başına gerçek foto şablon overrides
    # {"<VAR>": {"template_url": str, "rect": {...}}}
    op.add_column("phone_models", sa.Column("mockup_variants", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("phone_models", "mockup_variants")
    op.drop_column("line_items", "kilif_varyasyon_2")
    op.drop_column("line_items", "kilif_varyasyon")
