"""canlı görünüm: ziyaretçi ülkesi

Ziyaretçinin ülkesi Cloudflare'in CF-IPCountry başlığından gelir (vitrin
proxy'si iletir). IP SAKLANMAZ — yalnız ISO-3166 alpha-2 ülke kodu; canlı
görünümdeki "Konuma göre oturumlar" ve küre bunu kullanır.

Revision ID: c7d8e9f0a1b2
Revises: b6c7d8e9f0a1
"""
from alembic import op
import sqlalchemy as sa

revision = "c7d8e9f0a1b2"
down_revision = "b6c7d8e9f0a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("storefront_presence",
                  sa.Column("country", sa.String(2), nullable=True))
    # Canlı görünüm her 10 sn'de "bugünün oturumları"nı ülkeye göre sayar
    op.create_index("ix_presence_store_first_seen", "storefront_presence",
                    ["store_id", "first_seen"])


def downgrade() -> None:
    op.drop_index("ix_presence_store_first_seen", table_name="storefront_presence")
    op.drop_column("storefront_presence", "country")
