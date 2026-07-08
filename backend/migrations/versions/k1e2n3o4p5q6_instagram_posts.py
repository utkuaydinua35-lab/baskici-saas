"""instagram icerik taslaklari: instagram_posts

Revision ID: k1e2n3o4p5q6
Revises: j0d1m2n3o4p5
Create Date: 2026-07-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "k1e2n3o4p5q6"
down_revision = "j0d1m2n3o4p5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "instagram_posts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("store_id", UUID(as_uuid=True),
                  sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=10), server_default="post", nullable=False),
        sa.Column("style", sa.String(length=10), server_default="mockup", nullable=False),
        sa.Column("status", sa.String(length=12), server_default="taslak", nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("hashtags", sa.Text(), nullable=True),
        sa.Column("image_path", sa.String(length=500), nullable=True),
        sa.Column("design_id", UUID(as_uuid=True),
                  sa.ForeignKey("designs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("feedback", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_instagram_posts_tenant_id", "instagram_posts", ["tenant_id"])
    op.create_index("ix_instagram_posts_store_id", "instagram_posts", ["store_id"])
    op.create_index("ix_instagram_posts_status", "instagram_posts", ["status"])


def downgrade() -> None:
    op.drop_index("ix_instagram_posts_status", table_name="instagram_posts")
    op.drop_index("ix_instagram_posts_store_id", table_name="instagram_posts")
    op.drop_index("ix_instagram_posts_tenant_id", table_name="instagram_posts")
    op.drop_table("instagram_posts")
