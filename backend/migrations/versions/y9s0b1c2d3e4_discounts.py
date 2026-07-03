"""indirim kuponlari: discount_codes + checkout_sessions indirim kolonlari

Revision ID: y9s0b1c2d3e4
Revises: x8r9a0b1c2d3
Create Date: 2026-07-03

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "y9s0b1c2d3e4"
down_revision = "x8r9a0b1c2d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discount_codes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("store_id", UUID(as_uuid=True),
                  sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("value", sa.Numeric(12, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("min_subtotal", sa.Numeric(12, 2), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usage_limit", sa.Integer(), nullable=True),
        sa.Column("usage_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("once_per_customer", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("store_id", "code", name="uq_discount_store_code"),
    )

    op.add_column("checkout_sessions", sa.Column("discount_code", sa.String(40), nullable=True))
    op.add_column("checkout_sessions", sa.Column(
        "discount_amount", sa.Numeric(12, 2), server_default=sa.text("0"), nullable=False))
    op.add_column("checkout_sessions", sa.Column(
        "discount_code_id", UUID(as_uuid=True),
        sa.ForeignKey("discount_codes.id", ondelete="SET NULL"), nullable=True))


def downgrade() -> None:
    op.drop_column("checkout_sessions", "discount_code_id")
    op.drop_column("checkout_sessions", "discount_amount")
    op.drop_column("checkout_sessions", "discount_code")
    op.drop_table("discount_codes")
