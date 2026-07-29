"""mold_status_history.payload — slot cikarma islemini geri alabilmek icin

Revision ID: g4b5c6d7e8f9
Revises: h5c6d7e8f9a0
Create Date: 2026-07-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "g4b5c6d7e8f9"
down_revision = "h5c6d7e8f9a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mold_status_history",
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("mold_status_history", "payload")
