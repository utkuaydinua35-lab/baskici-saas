"""vitrin_oturumlari — oturum/kaynak/dönüşüm raporu (Shopify "Oturumlar")

Revision ID: v5t6o7r8m9n0
Revises: k4r5g6o7m8b1
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "v5t6o7r8m9n0"
down_revision = "k4r5g6o7m8b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vitrin_oturumlari",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ziyaretci", sa.String(64), nullable=False),
        sa.Column("basladi", sa.DateTime(timezone=True), nullable=False),
        sa.Column("son", sa.DateTime(timezone=True), nullable=False),
        sa.Column("giris_yolu", sa.String(300)),
        sa.Column("son_yol", sa.String(300)),
        sa.Column("sayfa_sayisi", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("kaynak", sa.String(30)),
        sa.Column("cihaz", sa.String(10)),
        sa.Column("ulke", sa.String(2)),
        sa.Column("urun_gordu", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("sepete_ekledi", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("odemeye_gecti", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_vitrin_oturumlari_tenant_id", "vitrin_oturumlari", ["tenant_id"])
    op.create_index("ix_vitrin_oturum_magaza_zaman", "vitrin_oturumlari", ["store_id", "basladi"])
    op.create_index("ix_vitrin_oturum_ziyaretci", "vitrin_oturumlari", ["store_id", "ziyaretci", "son"])


def downgrade() -> None:
    op.drop_table("vitrin_oturumlari")
