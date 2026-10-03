"""Bayi ↔ atölye sohbeti: bayi_sohbetleri + bayi_sohbet_mesajlari

Bayi panelden yazabilsin, görsel ve sipariş ekleyebilsin, aciliyet belirtebilsin.

Revision ID: b1a2s0h0b3t1
Revises: e8f9a0b1c2d3
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b1a2s0h0b3t1"
down_revision = "e8f9a0b1c2d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bayi_sohbetleri",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dealer_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("dealers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("son_mesaj_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("son_mesaj_ozet", sa.String(200), nullable=True),
        sa.Column("son_gonderen", sa.String(10), nullable=True),
        sa.Column("okunmamis_atolye", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("okunmamis_bayi", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("acil_bekliyor", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("dealer_id", name="uq_bayi_sohbet_dealer"),
    )
    op.create_index("ix_bayi_sohbetleri_tenant_id", "bayi_sohbetleri", ["tenant_id"])
    op.create_index("ix_bayi_sohbetleri_dealer_id", "bayi_sohbetleri", ["dealer_id"])
    op.create_index("ix_bayi_sohbetleri_son_mesaj_at", "bayi_sohbetleri", ["son_mesaj_at"])

    op.create_table(
        "bayi_sohbet_mesajlari",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sohbet_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("bayi_sohbetleri.id", ondelete="CASCADE"), nullable=False),
        sa.Column("gonderen", sa.String(10), nullable=False),
        sa.Column("gonderen_ad", sa.String(200), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("order_no", sa.String(50), nullable=True),
        sa.Column("aciliyet", sa.String(10), nullable=False, server_default=sa.text("'normal'")),
        sa.Column("okundu", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_bayi_sohbet_mesajlari_sohbet_id", "bayi_sohbet_mesajlari", ["sohbet_id"])
    op.create_index("ix_bayi_sohbet_mesajlari_order_id", "bayi_sohbet_mesajlari", ["order_id"])
    op.create_index("ix_bayi_sohbet_mesajlari_created_at", "bayi_sohbet_mesajlari", ["created_at"])


def downgrade() -> None:
    op.drop_table("bayi_sohbet_mesajlari")
    op.drop_table("bayi_sohbetleri")
