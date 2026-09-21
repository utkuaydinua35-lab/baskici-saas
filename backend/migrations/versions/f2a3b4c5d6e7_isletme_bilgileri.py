"""işletme bilgileri: BERNZ'in iş kuralları koddan mağaza ayarına

Vitrinde şu cümleler KODA SABİT yazılıydı ve her yeni mağazaya aynen
gidiyordu:
  • "Siparişinize özel üretilir, 1–3 iş gününde kargoya verilir"
  • "Özel tasarım baskılı telefon kılıfları…" (varsayılan SEO açıklaması)
  • mesafeli satış sözleşmesinde "baskılı telefon kılıfı", "1–3 iş günü"
  • iade sayfasında kişiye özel üretim → cayma hakkı istisnası
Bunlar BERNZ'in taahhütleri. Sistemi kiralayan başka bir işletmenin
müşterisine yanlış teslim süresi ya da hukuken geçersiz bir iade istisnası
göstermek ciddi bir sorun.

Artık dört mağaza ayarı var (store.config):
  isletme_urun_turu      "telefon kılıfı"
  isletme_tanitim        bir cümlelik tanıtım / SEO açıklaması
  isletme_teslim_suresi  "1–3 iş günü"
  isletme_kisiye_ozel    true → iade istisnası ve üretim notu gösterilir

MEVCUT mağazalar bugün gördükleri değerlerle tohumlanır — bu migration'dan
sonra var olan hiçbir vitrinde tek kelime değişmez. Sağ taraftaki `||`
mevcut anahtarları korur: elle girilmiş bir değer ASLA ezilmez.
YENİ mağazalar boş başlar; boş ayar → vitrin o cümleyi hiç yazmaz.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
"""
from alembic import op

revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE stores
        SET config = jsonb_build_object(
                'isletme_urun_turu',     'telefon kılıfı',
                'isletme_tanitim',       'Özel tasarım baskılı telefon kılıfları. Yüzlerce model için kişiye özel üretim, hızlı kargo.',
                'isletme_teslim_suresi', '1–3 iş günü',
                'isletme_kisiye_ozel',   true
            ) || COALESCE(config, '{}'::jsonb)
        WHERE platform = 'storefront'
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE stores
        SET config = config - 'isletme_urun_turu' - 'isletme_tanitim'
                            - 'isletme_teslim_suresi' - 'isletme_kisiye_ozel'
        WHERE platform = 'storefront'
    """)
