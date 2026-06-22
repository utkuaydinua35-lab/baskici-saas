"""notes tablosu (siparis notlari - apple notes tarzi)

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-06-17

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d5e6f7a8b9c0"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("dealer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("note_type", sa.String(length=20), nullable=False, server_default="acik"),
        sa.Column("baslik", sa.String(length=200), nullable=False),
        sa.Column("auto_content", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("manual_content", sa.Text(), nullable=True),
        sa.Column("is_serbest", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dealer_id"], ["dealers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notes_tenant_id", "notes", ["tenant_id"])
    op.create_index("ix_notes_store_id", "notes", ["store_id"])
    op.create_index("ix_notes_dealer_id", "notes", ["dealer_id"])
    op.create_index("ix_notes_note_type", "notes", ["note_type"])


def downgrade() -> None:
    op.drop_table("notes")
