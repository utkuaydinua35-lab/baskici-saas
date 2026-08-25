"""Bekleyen Shopify OAuth kurulumu — sırrı state JWT'sinden çıkar

Revision ID: z3c4d5e6f7a8
Revises: y2b3c4d5e6f7
"""
from alembic import op
import sqlalchemy as sa

revision = "z3c4d5e6f7a8"
down_revision = "y2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shopify_oauth_pending",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("store_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=True),
        sa.Column("shop", sa.String(255), nullable=False),
        sa.Column("client_id", sa.String(255), nullable=False),
        sa.Column("client_secret", sa.Text(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("scopes", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_shopify_oauth_pending_tenant_id",
                    "shopify_oauth_pending", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_shopify_oauth_pending_tenant_id",
                  table_name="shopify_oauth_pending")
    op.drop_table("shopify_oauth_pending")
