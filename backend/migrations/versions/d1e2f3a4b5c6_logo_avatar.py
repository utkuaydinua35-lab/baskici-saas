"""tenant.logo_url + user.avatar_url

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa

revision = "d1e2f3a4b5c6"
down_revision = "c0d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tenants", sa.Column("logo_url", sa.String(500), nullable=True))
    op.add_column("users", sa.Column("avatar_url", sa.String(500), nullable=True))


def downgrade():
    op.drop_column("users", "avatar_url")
    op.drop_column("tenants", "logo_url")
