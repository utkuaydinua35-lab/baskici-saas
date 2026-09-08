"""kullanici oturum iptali (sessions_valid_from)

JWT durumsuz olduğu için üretilen token 7 gün boyunca geri alınamıyordu:
parola değiştirmek mevcut oturumları DÜŞÜRMÜYORDU. Bu alan dolduğunda
token'ın `iat`'i bundan eskiyse token reddedilir.

Revision ID: ae62c4a8aaab
Revises: d7a8b9c0e1f2
"""
from alembic import op
import sqlalchemy as sa

revision = "ae62c4a8aaab"
down_revision = "d7a8b9c0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NULL = "hiç iptal edilmedi" — mevcut oturumlar bozulmasın diye
    # geriye dönük doldurma YAPILMIYOR.
    op.add_column(
        "users",
        sa.Column("sessions_valid_from", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "sessions_valid_from")
