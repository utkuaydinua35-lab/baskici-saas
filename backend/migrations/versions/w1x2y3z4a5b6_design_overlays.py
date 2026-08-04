"""hazır tasarım şablonları (overlay) — müşteri tasarımının üstüne binen çerçeveler

Revision ID: w1x2y3z4a5b6
Revises: v9e0f1a2b3c4
Create Date: 2026-08-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "w1x2y3z4a5b6"
down_revision = "v9e0f1a2b3c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "design_overlays",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("case_template_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("case_templates.id", ondelete="CASCADE"), nullable=True),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("image_path", sa.String(500), nullable=False),
        sa.Column("thumb_path", sa.String(500), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_design_overlays_tenant_id", "design_overlays", ["tenant_id"])
    op.create_index("ix_design_overlays_store_id", "design_overlays", ["store_id"])
    op.create_index("ix_design_overlays_case_template_id", "design_overlays",
                    ["case_template_id"])


def downgrade() -> None:
    op.drop_index("ix_design_overlays_case_template_id", table_name="design_overlays")
    op.drop_index("ix_design_overlays_store_id", table_name="design_overlays")
    op.drop_index("ix_design_overlays_tenant_id", table_name="design_overlays")
    op.drop_table("design_overlays")
