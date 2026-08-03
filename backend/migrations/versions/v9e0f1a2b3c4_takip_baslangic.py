"""tenants.takip_baslangic — toplu takip listesi baslangic tarihi

Sisteme gecmeden onceki birikmis gonderiler "takip numarasi bekleyen" listesini
dolduruyordu (228 kayit). Bu tarihten ONCE kargoya verilmis gonderiler artik
listelenmiyor.

MEVCUT kiracilar icin deger = migration'in calistigi an. Yani deploy anindan
onceki her sey listeden duser, sonrasi normal akisla gelir. Sonradan panelden
degistirilebilir; NULL yapilirsa tumu yeniden gorunur.

Revision ID: v9e0f1a2b3c4
Revises: u8d9e0f1a2b3
"""
from alembic import op
import sqlalchemy as sa

revision = "v9e0f1a2b3c4"
down_revision = "u8d9e0f1a2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("takip_baslangic", sa.DateTime(timezone=True), nullable=True),
    )
    # Mevcut kiracilar: "su andan itibaren". Yeni kiracilar NULL kalir —
    # gecmisleri olmadigi icin filtrelenecek bir birikim de yok.
    op.execute("UPDATE tenants SET takip_baslangic = now()")


def downgrade() -> None:
    op.drop_column("tenants", "takip_baslangic")
