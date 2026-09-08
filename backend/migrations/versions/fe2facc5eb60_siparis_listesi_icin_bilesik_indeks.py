"""siparis listesi icin bilesik indeks

Sipariş listesi (tenant + en yeni önce) tam tarama + sıralama yapıyordu.
Ölçüm:
  · CANLI (4.319 sipariş): sorgu 22,8 ms, Seq Scan.
  · YEREL (8.153 sipariş): sorgu 4,59 ms → 0,01 ms; GERÇEK UÇ 27,8 ms → 19,2 ms
    (ortanca, 7 ölçüm). Kazancın asıl değeri sabit maliyet: tarama satır
    sayısıyla doğrusal büyüyordu.

Kısmi indeks (deleted_at IS NULL) bilinçli: global soft-delete süzgeci ZATEN
her ORM sorgusuna bu koşulu ekliyor, dolayısıyla indeks tüm normal sorgulara
uyuyor ve çöpteki satırları taşımadığı için daha küçük kalıyor.

Revision ID: fe2facc5eb60
Revises: ae62c4a8aaab
"""
from alembic import op

revision = "fe2facc5eb60"
down_revision = "ae62c4a8aaab"
branch_labels = None
depends_on = None

_AD = "ix_orders_tenant_created_canli"


def upgrade() -> None:
    # CONCURRENTLY kullanılmıyor: alembic işlem (transaction) içinde çalışıyor
    # ve CONCURRENTLY transaction'da yasak. Tablo küçük (binler), kilit süresi
    # milisaniyeler — deploy penceresinde sorun değil.
    op.execute(
        f"CREATE INDEX IF NOT EXISTS {_AD} "
        "ON orders (tenant_id, created_at_platform DESC) "
        "WHERE deleted_at IS NULL"
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {_AD}")
