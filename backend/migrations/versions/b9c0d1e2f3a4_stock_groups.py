"""stock_groups + stock_items.group_id

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-06-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "b9c0d1e2f3a4"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stock_groups",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("linked_products", JSONB, server_default=sa.text("'[]'::jsonb")),
        sa.Column("low_stock_threshold", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "name", name="uq_stock_group_tenant_name"),
    )
    op.add_column("stock_items", sa.Column("group_id", UUID(as_uuid=True),
                  sa.ForeignKey("stock_groups.id", ondelete="CASCADE"), nullable=True))
    op.create_index("ix_stock_items_group_id", "stock_items", ["group_id"])


def downgrade():
    op.drop_index("ix_stock_items_group_id", "stock_items")
    op.drop_column("stock_items", "group_id")
    op.drop_table("stock_groups")
