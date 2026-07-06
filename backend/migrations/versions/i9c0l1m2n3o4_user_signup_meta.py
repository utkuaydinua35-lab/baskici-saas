"""kayit meta: users.signup_ip + signup_user_agent

Revision ID: i9c0l1m2n3o4
Revises: h8b9k0l1m2n3
Create Date: 2026-07-06

Not: onceki surumde bu migration yanlislikla 'e5y6h7i8j9k0' id'siyle olusturulup
panel/vitrin migration'i (variant_brand) ile cakismisti; zincirin sonuna tasindi.
"""
from alembic import op
import sqlalchemy as sa


revision = "i9c0l1m2n3o4"
down_revision = "h8b9k0l1m2n3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("signup_ip", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("signup_user_agent", sa.String(length=400), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "signup_user_agent")
    op.drop_column("users", "signup_ip")
