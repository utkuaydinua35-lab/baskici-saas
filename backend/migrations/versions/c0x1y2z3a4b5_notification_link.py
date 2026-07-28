"""notification link (bildirime tiklayinca ilgili sayfaya git)

Revision ID: c0x1y2z3a4b5
Revises: b9w0x1y2z3a4
Create Date: 2026-07-28
"""
from alembic import op
import sqlalchemy as sa

revision = "c0x1y2z3a4b5"
down_revision = "b9w0x1y2z3a4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("notifications", sa.Column("link", sa.String(length=300), nullable=True))


def downgrade():
    op.drop_column("notifications", "link")
