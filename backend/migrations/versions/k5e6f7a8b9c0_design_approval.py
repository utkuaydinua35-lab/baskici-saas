"""design_approvals — müşteri tasarım onay linki

Revision ID: k5e6f7a8b9c0
Revises: j4d5e6f7a8b9
Create Date: 2026-06-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "k5e6f7a8b9c0"
down_revision = "j4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "design_approvals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'bekliyor'")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("items", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("customer_note", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_design_approvals_tenant_id", "design_approvals", ["tenant_id"])
    op.create_index("ix_design_approvals_order_id", "design_approvals", ["order_id"])
    op.create_index("ix_design_approvals_token", "design_approvals", ["token"], unique=True)
    op.create_index("ix_design_approvals_status", "design_approvals", ["status"])


def downgrade() -> None:
    op.drop_index("ix_design_approvals_status", table_name="design_approvals")
    op.drop_index("ix_design_approvals_token", table_name="design_approvals")
    op.drop_index("ix_design_approvals_order_id", table_name="design_approvals")
    op.drop_index("ix_design_approvals_tenant_id", table_name="design_approvals")
    op.drop_table("design_approvals")
