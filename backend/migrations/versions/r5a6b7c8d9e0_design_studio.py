"""tasarim studyosu — case_templates + design_assets + customer_designs

Musterinin kendi kilifini tasarlayip hesabina kaydetmesi. Baski alani
oransal (0-1) tutulur; baskiya hazir dosya print_width_mm/dpi'dan uretilir.

Revision ID: r5a6b7c8d9e0
Revises: q4f5a6b7c8d9
Create Date: 2026-08-02
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "r5a6b7c8d9e0"
down_revision = "q4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "case_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("store_id", UUID(as_uuid=True),
                  sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(40), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("description", sa.String(300), nullable=True),
        sa.Column("image_path", sa.String(500), nullable=True),
        sa.Column("area_x", sa.Numeric(6, 4), server_default="0.1"),
        sa.Column("area_y", sa.Numeric(6, 4), server_default="0.1"),
        sa.Column("area_w", sa.Numeric(6, 4), server_default="0.8"),
        sa.Column("area_h", sa.Numeric(6, 4), server_default="0.8"),
        sa.Column("print_width_mm", sa.Integer(), server_default="70"),
        sa.Column("print_height_mm", sa.Integer(), server_default="145"),
        sa.Column("print_dpi", sa.Integer(), server_default="300"),
        sa.Column("position", sa.Integer(), server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("store_id", "key", name="uq_case_template_store_key"),
    )
    op.create_index("ix_case_templates_tenant_id", "case_templates", ["tenant_id"])
    op.create_index("ix_case_templates_store_id", "case_templates", ["store_id"])

    op.create_table(
        "design_assets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("store_id", UUID(as_uuid=True),
                  sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True),
                  sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=True),
        sa.Column("original_path", sa.String(500), nullable=False),
        sa.Column("preview_path", sa.String(500), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("bytes_size", sa.Integer(), nullable=True),
        sa.Column("filename", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_design_assets_tenant_id", "design_assets", ["tenant_id"])
    op.create_index("ix_design_assets_store_id", "design_assets", ["store_id"])
    op.create_index("ix_design_assets_customer_id", "design_assets", ["customer_id"])

    op.create_table(
        "customer_designs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("store_id", UUID(as_uuid=True),
                  sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True),
                  sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), server_default="Tasarımım"),
        sa.Column("template_key", sa.String(40), nullable=True),
        sa.Column("variant_id", UUID(as_uuid=True),
                  sa.ForeignKey("catalog_variants.id", ondelete="SET NULL"), nullable=True),
        sa.Column("layers", JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("preview_path", sa.String(500), nullable=True),
        sa.Column("print_path", sa.String(500), nullable=True),
        sa.Column("status", sa.String(12), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("order_id", UUID(as_uuid=True),
                  sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_customer_designs_tenant_id", "customer_designs", ["tenant_id"])
    op.create_index("ix_customer_designs_store_id", "customer_designs", ["store_id"])
    op.create_index("ix_customer_designs_customer_id", "customer_designs", ["customer_id"])
    op.create_index("ix_customer_designs_status", "customer_designs", ["status"])


def downgrade() -> None:
    op.drop_table("customer_designs")
    op.drop_table("design_assets")
    op.drop_table("case_templates")
