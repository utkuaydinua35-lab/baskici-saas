"""paket tracker — tracker_order_stages

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tracker_order_stages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("store_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("stores.id", ondelete="SET NULL"), nullable=True),
        sa.Column("shopify_order_id", sa.String(length=50), nullable=False),
        sa.Column("order_number", sa.String(length=50), nullable=True),
        sa.Column("stage_id", sa.String(length=40), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("shopify_order_id", name="uq_tracker_stage_order"),
    )
    op.create_index("ix_tracker_stages_order_number", "tracker_order_stages", ["order_number"])


def downgrade() -> None:
    op.drop_index("ix_tracker_stages_order_number", table_name="tracker_order_stages")
    op.drop_table("tracker_order_stages")
