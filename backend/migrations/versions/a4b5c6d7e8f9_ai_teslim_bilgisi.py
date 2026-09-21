"""AI destek: teslim kuralları koddan mağaza ayarına

AI yanıt taslağı BERNZ'in iç teslim kurallarını ("iPhone 7 iş günü, Android
10–14…") ve "Sen BERNZ adlı…" kimliğini KODDAN alıyordu. Sonuç: 505 Cover ve
Lunera müşterilerine de BERNZ adıyla yazılıyordu; sistem kiralandığında başka
bir işletmenin müşterisine BERNZ'in süreleri söylenecekti.

Kimlik artık konuşmanın mağazasından, teslim kuralları
store.config["ai_teslim_bilgisi"]'nden okunuyor.

VAR OLAN tüm mağazalara bugünkü metin tohumlanır → AI'nın teslim cevapları
değişmez. Elle girilmiş bir değer ezilmez. Yeni mağazalar boş başlar; boşsa
AI kısa teslim süresine (isletme_teslim_suresi) düşer, o da yoksa süre
UYDURMAZ ve yer tutucu bırakır.

Revision ID: a4b5c6d7e8f9
Revises: f2a3b4c5d6e7
"""
import sqlalchemy as sa
from alembic import op

revision = "a4b5c6d7e8f9"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None

METIN = (
    "TESLİM SÜRELERİ (iş günü; Cumartesi/Pazar hariç. Tahmini sürelerdir, "
    "toptancı yoğunluğuna göre değişebilir):\n"
    "- iPhone modelleri (normal kılıf): ortalama 7 iş günü içinde kargoya verilir.\n"
    "- Parlak, Şeffaf ve MagSafe kılıflar: ortalama 10–14 iş günü.\n"
    "- Android modeller: ortalama 10–14 iş günü.\n"
    "- Kişiye özel tasarımlar: ortalama 10–15 iş günü, azami 30 iş günü (tasarım sırasına bağlı).\n"
    "- Android, MagSafe ve Parlak kılıflar talep üzerine tedarik edilir; azami 30 iş "
    "gününe kadar bekletme hakkı saklıdır.\n"
    "Karışık siparişte teslim süresi, en uzun süreli kaleme göre belirlenir. Kesin gün/tarih "
    "verme; \"ortalama\", \"tahmini\" ve aralık (ör. 10–14 iş günü) ifadeleri kullan."
)


def upgrade() -> None:
    op.execute(sa.text(
        "UPDATE stores SET config = jsonb_build_object('ai_teslim_bilgisi', CAST(:m AS text)) "
        "|| COALESCE(config, '{}'::jsonb)"
    ).bindparams(m=METIN))


def downgrade() -> None:
    op.execute("UPDATE stores SET config = config - 'ai_teslim_bilgisi'")
