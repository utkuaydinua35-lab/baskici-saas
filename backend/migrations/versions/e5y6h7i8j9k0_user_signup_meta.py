"""kayit meta: users.signup_ip + signup_user_agent

Revision ID: e5y6h7i8j9k0
Revises: d4x5g6h7i8j9
Create Date: 2026-07-06

"""
from alembic import op
import sqlalchemy as sa


revision = "e5y6h7i8j9k0"
down_revision = "d4x5g6h7i8j9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("signup_ip", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("signup_user_agent", sa.String(length=400), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "signup_user_agent")
    op.drop_column("users", "signup_ip")
