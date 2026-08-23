"""Bayi portalı — users.dealer_id + orders.bayii_onay_bekliyor

Bayiler kendi panellerinden sipariş girecek. Kullanıcı bir bayiye bağlanır ve
yalnızca o bayinin verisini görür. Bayinin girdiği sipariş ONAY BEKLER:
yönetici varyasyonu seçip onaylayana kadar kalıba girmez ve cari borç işlenmez.

Revision ID: x1a2b3c4d5e6
Revises: w0f1a2b3c4d5
"""
from alembic import op
import sqlalchemy as sa

revision = "x1a2b3c4d5e6"
down_revision = "w0f1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("dealer_id", sa.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_users_dealer_id", "users", ["dealer_id"])
    op.create_foreign_key("fk_users_dealer", "users", "dealers",
                          ["dealer_id"], ["id"], ondelete="CASCADE")

    op.add_column("orders", sa.Column(
        "bayii_onay_bekliyor", sa.Boolean(), nullable=False,
        server_default=sa.text("false")))
    op.create_index("ix_orders_bayii_onay_bekliyor", "orders", ["bayii_onay_bekliyor"])


def downgrade() -> None:
    op.drop_index("ix_orders_bayii_onay_bekliyor", table_name="orders")
    op.drop_column("orders", "bayii_onay_bekliyor")
    op.drop_constraint("fk_users_dealer", "users", type_="foreignkey")
    op.drop_index("ix_users_dealer_id", table_name="users")
    op.drop_column("users", "dealer_id")
