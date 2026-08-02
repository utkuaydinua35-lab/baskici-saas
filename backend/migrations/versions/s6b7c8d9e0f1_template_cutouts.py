"""kilif sablonu — baski alani koşe yuvarlakligi + basilamayan bolgeler

Panelde imlecle secilen alanlarin ovalligi ve kamera/MagSafe kesikleri.

Revision ID: s6b7c8d9e0f1
Revises: r5a6b7c8d9e0
Create Date: 2026-08-02
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "s6b7c8d9e0f1"
down_revision = "r5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("case_templates", sa.Column(
        "area_radius", sa.Numeric(6, 4), server_default="0.08"))
    op.add_column("case_templates", sa.Column(
        "cutouts", JSONB(), server_default=sa.text("'[]'::jsonb")))


def downgrade() -> None:
    op.drop_column("case_templates", "cutouts")
    op.drop_column("case_templates", "area_radius")
