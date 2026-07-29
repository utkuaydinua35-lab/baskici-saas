"""login_attempts tablosu + users.password_login_disabled

Revision ID: d1y2z3a4b5c6
Revises: c0x1y2z3a4b5
Create Date: 2026-07-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d1y2z3a4b5c6"
down_revision = "c0x1y2z3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "login_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(400), nullable=True),
        sa.Column("reason", sa.String(30), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_login_attempts_email", "login_attempts", ["email"])
    op.create_index("ix_login_attempts_ip", "login_attempts", ["ip"])
    op.create_index("ix_login_attempts_reason", "login_attempts", ["reason"])
    op.create_index("ix_login_attempts_created_at", "login_attempts", ["created_at"])

    op.add_column(
        "users",
        sa.Column("password_login_disabled", sa.Boolean(),
                  server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "password_login_disabled")
    op.drop_index("ix_login_attempts_created_at", table_name="login_attempts")
    op.drop_index("ix_login_attempts_reason", table_name="login_attempts")
    op.drop_index("ix_login_attempts_ip", table_name="login_attempts")
    op.drop_index("ix_login_attempts_email", table_name="login_attempts")
    op.drop_table("login_attempts")
