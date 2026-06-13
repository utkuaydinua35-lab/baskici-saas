"""user.permissions

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-06-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("permissions", JSONB(), nullable=False, server_default="[]"))


def downgrade():
    op.drop_column("users", "permissions")
