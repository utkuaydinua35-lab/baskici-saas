"""vitrin musteri hesaplari: adres + sifresiz giris kodu alanlari

Revision ID: g7a8j9k0l1m2
Revises: f6z7i8j9k0l1
Create Date: 2026-07-05

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "g7a8j9k0l1m2"
down_revision = "f6z7i8j9k0l1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("default_address", JSONB(), nullable=True))
    op.add_column("customers", sa.Column("login_code_hash", sa.String(255), nullable=True))
    op.add_column("customers", sa.Column("login_code_expires", sa.DateTime(timezone=True), nullable=True))
    op.add_column("customers", sa.Column(
        "login_code_attempts", sa.Integer(), server_default=sa.text("0"), nullable=False))


def downgrade() -> None:
    op.drop_column("customers", "login_code_attempts")
    op.drop_column("customers", "login_code_expires")
    op.drop_column("customers", "login_code_hash")
    op.drop_column("customers", "default_address")
