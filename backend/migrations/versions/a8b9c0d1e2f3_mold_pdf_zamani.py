"""mold pdf_indirilme_zamani

Revision ID: a8b9c0d1e2f3
Revises: f1e2d3c4b5a6
Create Date: 2026-06-11

"""
from alembic import op
import sqlalchemy as sa

revision = "a8b9c0d1e2f3"
down_revision = "f1e2d3c4b5a6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("molds", sa.Column("pdf_indirilme_zamani", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("molds", "pdf_indirilme_zamani")
