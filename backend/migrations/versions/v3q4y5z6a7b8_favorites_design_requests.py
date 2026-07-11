"""Hesap favorileri + tasarım talepleri

Revision ID: v3q4y5z6a7b8
Revises: u2p3x4y5z6a7
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "v3q4y5z6a7b8"
down_revision = "u2p3x4y5z6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("favorites", JSONB(), nullable=True))
    op.create_table(
        "design_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("store_id", UUID(as_uuid=True),
                  sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("customer_email", sa.String(200), nullable=False),
        sa.Column("customer_name", sa.String(200), nullable=True),
        sa.Column("image_url", sa.String(500), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("phone_model", sa.String(120), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="acik"),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("design_requests")
    op.drop_column("customers", "favorites")
