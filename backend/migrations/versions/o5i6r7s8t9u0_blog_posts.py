"""Vitrin blogu: blog_posts

Revision ID: o5i6r7s8t9u0
Revises: n4h5q6r7s8t9
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "o5i6r7s8t9u0"
down_revision = "n4h5q6r7s8t9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "blog_posts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("store_id", UUID(as_uuid=True),
                  sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("slug", sa.String(220), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("excerpt", sa.String(500), nullable=True),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("cover_url", sa.String(500), nullable=True),
        sa.Column("seo_title", sa.String(300), nullable=True),
        sa.Column("seo_description", sa.String(500), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("store_id", "slug", name="uq_blog_store_slug"),
    )


def downgrade() -> None:
    op.drop_table("blog_posts")
