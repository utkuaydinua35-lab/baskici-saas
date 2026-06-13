"""user.pin_hash

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-06-13
"""
from alembic import op
import sqlalchemy as sa

revision = "f3a4b5c6d7e8"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("pin_hash", sa.String(255), nullable=True))


def downgrade():
    op.drop_column("users", "pin_hash")
