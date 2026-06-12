"""stock_items.models (coklu uyumlu model)

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-06-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "c0d1e2f3a4b5"
down_revision = "b9c0d1e2f3a4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("stock_items", sa.Column("models", JSONB, server_default=sa.text("'[]'::jsonb")))
    # Mevcut tek-model kalemleri models listesine kopyala
    op.execute("UPDATE stock_items SET models = to_jsonb(ARRAY[model]) WHERE model IS NOT NULL AND (models IS NULL OR models = '[]'::jsonb)")


def downgrade():
    op.drop_column("stock_items", "models")
