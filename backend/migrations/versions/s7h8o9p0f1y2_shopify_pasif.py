"""Shopify mağazalarını pasife al, eski uyarılarını okundu say

Shopify aboneliği ödenmediği için API "402 Payment Required" dönüyor: saatlik
senkron her gün hata bildirimi açıyor, kargoda Shopify'a yazma denemesi uyarı
bildirimi ve Telegram mesajı üretiyordu.

Mağaza SİLİNMEZ: ortak tasarım havuzunun tasarımları ve geçmiş siparişler onun
altında (silmek cascade ile hepsini uçurur). Yalnız pasife alınır:
senkron, "siparişleri çek" ve Shopify'a kargo yazma durur. Geri almak için
panelden mağazayı tekrar aktif etmek yeter.

Bildirimler silinmez, okundu işaretlenir.

Revision ID: s7h8o9p0f1y2
Revises: v8a9r0g1o2r3
"""
from alembic import op

revision = "s7h8o9p0f1y2"
down_revision = "v8a9r0g1o2r3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE notifications SET is_read = true
         WHERE is_read = false
           AND store_id IN (SELECT id FROM stores WHERE platform = 'shopify')
    """)
    op.execute("UPDATE stores SET is_active = false WHERE platform = 'shopify'")


def downgrade() -> None:
    # Bilerek boş: hangi mağazanın daha önce aktif olduğu bilgisi tutulmuyor;
    # geri almak için panelden mağazayı tekrar aktif edin.
    pass
