"""white-label: tenants.brand_color/app_name + users.is_platform_admin

Revision ID: l6f7a8b9c0d1
Revises: k5e6f7a8b9c0
Create Date: 2026-06-26

"""
from alembic import op
import sqlalchemy as sa

revision = "l6f7a8b9c0d1"
down_revision = "k5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("brand_color", sa.String(20), nullable=True))
    op.add_column("tenants", sa.Column("app_name", sa.String(80), nullable=True))
    op.add_column("users", sa.Column(
        "is_platform_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")))


def downgrade() -> None:
    op.drop_column("users", "is_platform_admin")
    op.drop_column("tenants", "app_name")
    op.drop_column("tenants", "brand_color")
