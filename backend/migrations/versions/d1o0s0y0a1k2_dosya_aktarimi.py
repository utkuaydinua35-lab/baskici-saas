"""dosya_aktarimlari — cihazlar arası geçici dosya aktarımı (24 saatte silinir)

Revision ID: d1o0s0y0a1k2
Revises: b2l0g0d3a1e2
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d1o0s0y0a1k2"
down_revision = "b2l0g0d3a1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dosya_aktarimlari",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("yukleyen", sa.String(200), nullable=True),
        sa.Column("dosya_adi", sa.String(300), nullable=False),
        sa.Column("yol", sa.String(500), nullable=False),
        sa.Column("boyut", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("tur", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_dosya_aktarimlari_tenant_id", "dosya_aktarimlari", ["tenant_id"])
    op.create_index("ix_dosya_aktarimlari_created_at", "dosya_aktarimlari", ["created_at"])
    op.create_index("ix_dosya_aktarimlari_expires_at", "dosya_aktarimlari", ["expires_at"])


def downgrade() -> None:
    op.drop_table("dosya_aktarimlari")
