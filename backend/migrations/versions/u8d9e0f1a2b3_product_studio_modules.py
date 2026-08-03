"""urun ↔ tasarim studyosu modulu — catalog_products.studio_templates

Urune baglanan kilif sablonlari (CaseTemplate.key listesi). Vitrin urun
sayfasinda "kendi tasarimini yap" secenekleri bundan uretilir.

Revision ID: u8d9e0f1a2b3
Revises: t7c8d9e0f1a2
Create Date: 2026-08-03
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "u8d9e0f1a2b3"
down_revision = "t7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("catalog_products", sa.Column(
        "studio_templates", JSONB(), server_default=sa.text("'[]'::jsonb")))


def downgrade() -> None:
    op.drop_column("catalog_products", "studio_templates")
