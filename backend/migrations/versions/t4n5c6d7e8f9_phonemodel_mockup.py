"""phone_models mockup: template_url + rect

Revision ID: t4n5c6d7e8f9
Revises: s3m4b5c6d7e8
Create Date: 2026-06-28

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "t4n5c6d7e8f9"
down_revision = "s3m4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("phone_models", sa.Column("mockup_template_url", sa.String(500), nullable=True))
    op.add_column("phone_models", sa.Column("mockup_rect", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("phone_models", "mockup_rect")
    op.drop_column("phone_models", "mockup_template_url")
