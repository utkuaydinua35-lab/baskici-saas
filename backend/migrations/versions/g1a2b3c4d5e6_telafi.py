"""telafi alanlari (orders): is_telafi, telafi_kaynak_order_id, telafi_sebep

Revision ID: g1a2b3c4d5e6
Revises: e6f7a8b9c0d1
Create Date: 2026-06-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "g1a2b3c4d5e6"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("is_telafi", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "orders",
        sa.Column("telafi_kaynak_order_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("telafi_sebep", sa.String(length=200), nullable=True),
    )
    op.create_index("ix_orders_is_telafi", "orders", ["is_telafi"])
    op.create_index(
        "ix_orders_telafi_kaynak_order_id", "orders", ["telafi_kaynak_order_id"]
    )
    op.create_foreign_key(
        "fk_orders_telafi_kaynak",
        "orders", "orders",
        ["telafi_kaynak_order_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_orders_telafi_kaynak", "orders", type_="foreignkey")
    op.drop_index("ix_orders_telafi_kaynak_order_id", table_name="orders")
    op.drop_index("ix_orders_is_telafi", table_name="orders")
    op.drop_column("orders", "telafi_sebep")
    op.drop_column("orders", "telafi_kaynak_order_id")
    op.drop_column("orders", "is_telafi")
