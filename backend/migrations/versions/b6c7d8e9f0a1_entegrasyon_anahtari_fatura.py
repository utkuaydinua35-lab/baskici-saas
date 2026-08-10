"""entegrasyon anahtarı + sipariş fatura durumu

Revision ID: b6c7d8e9f0a1
Revises: a5b6c7d8e9f0
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b6c7d8e9f0a1"
down_revision = "a5b6c7d8e9f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("key_prefix", sa.String(16), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_ip", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_integration_keys_tenant_id", "integration_keys", ["tenant_id"])
    op.create_index("ix_integration_keys_store_id", "integration_keys", ["store_id"])
    op.create_index("ix_integration_keys_key_hash", "integration_keys", ["key_hash"],
                    unique=True)

    op.add_column("orders", sa.Column("fatura_durum", sa.String(20), nullable=True))
    op.add_column("orders", sa.Column("fatura", postgresql.JSONB(), nullable=True))
    op.create_index("ix_orders_fatura_durum", "orders", ["fatura_durum"])


def downgrade() -> None:
    op.drop_index("ix_orders_fatura_durum", table_name="orders")
    op.drop_column("orders", "fatura")
    op.drop_column("orders", "fatura_durum")
    op.drop_index("ix_integration_keys_key_hash", table_name="integration_keys")
    op.drop_index("ix_integration_keys_store_id", table_name="integration_keys")
    op.drop_index("ix_integration_keys_tenant_id", table_name="integration_keys")
    op.drop_table("integration_keys")
