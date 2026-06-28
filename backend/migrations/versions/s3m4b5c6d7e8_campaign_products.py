"""campaign products: urun kartlari izgarasi (JSONB)

Revision ID: s3m4b5c6d7e8
Revises: r2l3a4b5c6d7
Create Date: 2026-06-28

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "s3m4b5c6d7e8"
down_revision = "r2l3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("marketing_campaigns",
                  sa.Column("products", JSONB(), server_default=sa.text("'[]'::jsonb")))


def downgrade() -> None:
    op.drop_column("marketing_campaigns", "products")
