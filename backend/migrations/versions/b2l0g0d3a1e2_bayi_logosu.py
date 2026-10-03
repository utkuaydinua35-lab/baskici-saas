"""dealers.logo_url — bayinin kendi logosu (sohbette avatar)

Revision ID: b2l0g0d3a1e2
Revises: b1a2s0h0b3t1
"""
from alembic import op
import sqlalchemy as sa

revision = "b2l0g0d3a1e2"
down_revision = "b1a2s0h0b3t1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("dealers", sa.Column("logo_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("dealers", "logo_url")
