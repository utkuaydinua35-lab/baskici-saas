"""campaign content: image_url + preheader + personalize

Revision ID: r2l3a4b5c6d7
Revises: q1k2f3a4b5c6
Create Date: 2026-06-28

"""
from alembic import op
import sqlalchemy as sa

revision = "r2l3a4b5c6d7"
down_revision = "q1k2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("marketing_campaigns", sa.Column("image_url", sa.String(500), nullable=True))
    op.add_column("marketing_campaigns", sa.Column("preheader", sa.String(200), nullable=True))
    op.add_column("marketing_campaigns",
                  sa.Column("personalize", sa.Boolean(), server_default=sa.text("false")))


def downgrade() -> None:
    op.drop_column("marketing_campaigns", "personalize")
    op.drop_column("marketing_campaigns", "preheader")
    op.drop_column("marketing_campaigns", "image_url")
