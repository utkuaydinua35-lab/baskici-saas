"""tenants.etiket_ayarlari — kargo etiketi şablon ayarları

Revision ID: b5e6f7a8c9d0
Revises: a4d5e6f7b8c9
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b5e6f7a8c9d0"
down_revision = "a4d5e6f7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column(
        "etiket_ayarlari", postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text("'{}'::jsonb"), nullable=False))


def downgrade() -> None:
    op.drop_column("tenants", "etiket_ayarlari")
