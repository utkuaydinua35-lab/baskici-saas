"""couple+kisiye ozel: line_item 2. tasarim/model + couple_products.is_kisiye_ozel

Revision ID: u5o6d7e8f9a0
Revises: t4n5c6d7e8f9
Create Date: 2026-06-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "u5o6d7e8f9a0"
down_revision = "t4n5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("line_items", sa.Column("assigned_design_id_2", UUID(as_uuid=True),
                  sa.ForeignKey("designs.id", ondelete="SET NULL"), nullable=True))
    op.add_column("line_items", sa.Column("device_model_override_2", sa.String(100), nullable=True))
    op.create_index("ix_line_items_assigned_design_id_2", "line_items", ["assigned_design_id_2"])
    op.add_column("couple_products", sa.Column("is_kisiye_ozel", sa.Boolean(),
                  server_default=sa.text("false"), nullable=False))


def downgrade() -> None:
    op.drop_column("couple_products", "is_kisiye_ozel")
    op.drop_index("ix_line_items_assigned_design_id_2", "line_items")
    op.drop_column("line_items", "device_model_override_2")
    op.drop_column("line_items", "assigned_design_id_2")
