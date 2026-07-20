"""storefront_presence — vitrin canli gorunum (live view) oturum ping'leri

Revision ID: a8v9w0x1y2z3
Revises: z7u8v9w0x1y2
Create Date: 2026-07-20
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "a8v9w0x1y2z3"
down_revision = "z7u8v9w0x1y2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "storefront_presence",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("store_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("session_key", sa.String(64), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_path", sa.String(300), nullable=True),
        sa.Column("cart_items", sa.Integer, nullable=False, server_default="0"),
        sa.UniqueConstraint("store_id", "session_key", name="uq_presence_store_key"),
    )
    op.create_index("ix_presence_store_last_seen", "storefront_presence",
                    ["store_id", "last_seen"])


def downgrade() -> None:
    op.drop_index("ix_presence_store_last_seen", table_name="storefront_presence")
    op.drop_table("storefront_presence")
