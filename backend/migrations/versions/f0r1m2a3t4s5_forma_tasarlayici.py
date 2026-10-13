"""design_overlays.forma — forma tasarlayıcı ayarı (desen/renk/yazı tipi/amblem)

Revision ID: f0r1m2a3t4s5
Revises: k9t1d2s3n4l5
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "f0r1m2a3t4s5"
down_revision = "k9t1d2s3n4l5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("design_overlays", sa.Column("forma", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("design_overlays", "forma")
