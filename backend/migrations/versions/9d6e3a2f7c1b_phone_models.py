"""paket telefon modelleri — phone_models overlay table

Revision ID: 9d6e3a2f7c1b
Revises: 8c5d2f1e9a4b
Create Date: 2026-06-06

phone_models: baseline (gizli case_dimensions) üzerine DB overlay.
tenant_id NULL → global; doluysa tenant'a özel. (tenant_id, spec_key) unique.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "9d6e3a2f7c1b"
down_revision = "8c5d2f1e9a4b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "phone_models",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("spec_key", sa.String(length=60), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("brand", sa.String(length=40), nullable=True),
        sa.Column("width_cm", sa.Float(), nullable=False),
        sa.Column("height_cm", sa.Float(), nullable=False),
        sa.Column("radius_cm", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "spec_key", name="uq_phone_model_tenant_key"),
    )
    op.create_index("ix_phone_models_tenant_id", "phone_models", ["tenant_id"])
    op.create_index("ix_phone_models_spec_key", "phone_models", ["spec_key"])


def downgrade() -> None:
    op.drop_index("ix_phone_models_spec_key", table_name="phone_models")
    op.drop_index("ix_phone_models_tenant_id", table_name="phone_models")
    op.drop_table("phone_models")
