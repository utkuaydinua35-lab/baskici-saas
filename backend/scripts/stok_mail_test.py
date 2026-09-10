"""Eksik stok e-postası — içerik, Türkçe yazım ve güvenlik.

Sahada görülen iki kusur burada sınanıyor:
  1. "SİYAH".capitalize() → "Si̇yah" (birleşen üst nokta). Müşteriye giden
     mailde tam olarak bu çıktı. Python'ın Türkçe İ tuzağı.
  2. Mail işlevsizdi: "bu e-postayı yanıtlayın" diyordu (destek sayfası yok)
     ve siparişte başka ne olduğunu göstermiyordu.

Ayrıca: ürün/müşteri adı e-postaya GÖMÜLÜYOR — HTML kaçırma şart.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import LineItem, Order  # noqa: E402
from app.services import email_service, siparis_ozet, stock_email  # noqa: E402
from app.services.tr_metin import baslik  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


db = SessionLocal()

print("\n── Türkçe büyük/küçük harf tuzağı ──")
# ⚠ Python "SİYAH".capitalize() çağrısında "Si̇yah" üretiyor: İ (U+0130)
# küçülürken i + U+0307 oluyor. Müşteriye giden mailde bu görüldü.
es("Python'ın kendi hatası hâlâ orada (tuzak gerçek)", "Si̇yah", "SİYAH".capitalize())
es("SİYAH → Siyah", "Siyah", baslik("SİYAH"))
es("birleşen nokta YOK", False, "̇" in baslik("SİYAH"))
es("ŞEFFAF → Şeffaf", "Şeffaf", baslik("ŞEFFAF"))
es("PARLAK → Parlak", "Parlak", baslik("PARLAK"))
es("BEYAZ → Beyaz", "Beyaz", baslik("BEYAZ"))
es("iki kelime: SİYAH MAT", "Siyah Mat", baslik("SİYAH MAT"))
es("İngilizce ad bozulmuyor", "Breaking Bad", baslik("BREAKING BAD"))
es("düzgün yazılmış ad AYNEN kalır", "Red Dead Redemption",
   baslik("Red Dead Redemption"))

print("\n── kalıp slot tanımı (mailin ürün satırı) ──")
from app.routers.molds import _slot_urun_adi  # noqa: E402


class _Slot:
    kalip_kodu = "IPHONE-15-PLUS-GROUP|SIYAH"
    model = "iPhone 15 Plus"


_ad = _slot_urun_adi(db, _Slot())
es("slot adında birleşen nokta YOK", False, "̇" in _ad)
es("varyasyon okunur", True, _ad.startswith("Siyah"))

print("\n── sipariş özeti (mailde ve sayfada AYNI kaynak) ──")
_oid = db.execute(select(LineItem.order_id).group_by(LineItem.order_id)
                  .having(func.count() > 1).limit(1)).scalar()
if _oid is None:
    print("  · çok kalemli sipariş yok — atlandı")
else:
    _ord = db.get(Order, _oid)
    _k = siparis_ozet.kalemler(db, _ord)
    es("kalemler döndü", True, len(_k) > 1)
    es("her kalemde ürün adı var", True, all(x["urun"] for x in _k))
    es("her kalemde durum var", True, all(x["durum"] for x in _k))
    _gecerli = {"Hazır", "Stok bekleniyor", "Üretimde", "Hazırlanıyor"}
    es("durumlar müşteri diliyle", True, {x["durum"] for x in _k} <= _gecerli)
    es("panel terimi sızmıyor", False,
       any("kalıba" in x["durum"].lower() or "_" in x["durum"] for x in _k))

    print("\n── mail gövdesi ──")
    _eski_mail, _eski_ad = _ord.customer_email, _ord.customer_name
    _gercek_gonder = stock_email.email_service.is_configured
    _el = __import__("app.services.email_log", fromlist=["x"])
    _gercek_kaydet = _el.gonder_ve_kaydet
    _yakalanan = {}

    def _sahte(db_, **kw):
        _yakalanan.update(kw)
        return True

    try:
        stock_email.email_service.is_configured = lambda: True
        _el.gonder_ve_kaydet = _sahte
        _ord.customer_email = "test@ornek.com"
        # ⚠ XSS: ürün ve müşteri adı e-postaya GÖMÜLÜYOR.
        _ord.customer_name = "<script>alert(1)</script> Ayşe"
        db.flush()
        ok, _ = stock_email.send_stok_eksik(db, _ord, 'Siyah "iPhone" <b>15</b>')
        _html = _yakalanan.get("html") or ""
        es("mail üretildi", True, ok and bool(_html))

        _destek = get_settings().support_public_base_url.rstrip("/")
        es("destek adresine link var", True, f"href='{_destek}'" in _html)
        es("'bu e-postayı yanıtlayın' KALKTI", False, "yanıtlamanız yeterli" in _html)
        es("takip/destek düğmesi var", True, "Siparişim hakkında yazın" in _html)

        es("sipariş içeriği tablosu var", True, "Siparişinizdeki ürünler" in _html)
        for _x in _k[:3]:
            es(f"kalem mailde: {_x['urun'][:28]}…", True,
               email_service and _x["urun"][:28].split("<")[0][:20] in _html)
        es("durum rozeti basıldı", True,
           any(f">{d}</span>" in _html for d in _gecerli))

        print("\n── HTML kaçırma (XSS) ──")
        es("script etiketi ham GİRMEDİ", False, "<script>alert(1)</script>" in _html)
        es("kaçırılmış hali var", True, "&lt;script&gt;" in _html)
        es("ürün adındaki <b> ham girmedi", False, "<b>15</b>" in _html)
    finally:
        stock_email.email_service.is_configured = _gercek_gonder
        _el.gonder_ve_kaydet = _gercek_kaydet
        _ord.customer_email, _ord.customer_name = _eski_mail, _eski_ad
        db.rollback()
        print("  · sipariş eski haline döndürüldü")

print("\n── tek kalemli siparişte tablo BASILMAZ (gürültü) ──")
_tek = db.execute(select(LineItem.order_id).group_by(LineItem.order_id)
                  .having(func.count() == 1).limit(1)).scalar()
if _tek is not None:
    es("tek kalemde tablo yok", "",
       stock_email._kalem_tablosu(db, db.get(Order, _tek), {}))
else:
    print("  · tek kalemli sipariş yok — atlandı")

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
