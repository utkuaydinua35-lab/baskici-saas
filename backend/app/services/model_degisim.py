"""Eksik stok → müşteriye WhatsApp mesajı + telefon modeli değiştirme bağlantısı.

AKIŞ
  1. Operatör kalemi stok yokluğu nedeniyle kalıptan çıkarır.
  2. "WhatsApp'tan bildir" derse burada 12 saatlik tek kullanımlık bir bağlantı
     üretilir ve hazır mesaj `wa.me` adresiyle döner.
  3. Operatör WhatsApp'ta gönder'e basar (mesaj hazır gelir).
  4. Müşteri bağlantıdan modelini — şeffaf/parlak kalıpta varyasyonunu da —
     değiştirir; kalem o an bir kalıptaysa kalıptan ÇEKİLİR.

NEDEN e-posta değil: müşteriler eksik stok mailinin ulaşmadığını bildirdi;
e-posta tarafında teslim kanıtımız da yok (bkz. services/email_service.py —
Resend mesaj kimliği saklanmıyor, bounce webhook'u yok). WhatsApp'ta mesajı
operatör kendi hesabından gönderdiği için teslim gözle görülüyor.

MESAJ NEDEN ÜÇ TÜRLÜ: müşteriye sunulabilecek seçenek, çıkarıldığı kalıba göre
değişiyor.
  · şeffaf  → model + varyasyon (baskılı ürünlerden biri)
  · parlak  → model + varyasyon (şeffaf ya da baskılı ürünlerden biri)
  · diğer   → yalnız model
Yanlış mesaj, müşteriye VERİLEMEYECEK bir seçenek vaat eder.
"""
from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ModelDegisimTalebi, Order

# Bağlantı ömrü. Kısa tutuluyor: stok ve üretim planı hızla değişiyor, 12 saat
# öncesinden gelen bir değişiklik çoktan basılmış kalıbı bozabilir.
GECERLILIK_SAAT = 12

SEFFAF, PARLAK, DIGER = "seffaf", "parlak", "diger"


def kalip_turu(mold_variation: str | None) -> str:
    """Kalıp varyasyonundan mesaj/seçenek türü."""
    v = (mold_variation or "").strip().upper()
    if v in ("ŞEFFAF", "SEFFAF"):
        return SEFFAF
    if v == "PARLAK":
        return PARLAK
    return DIGER


# ─── Telefon ──────────────────────────────────────────────────────────────
def telefon_normalize(ham: str | None) -> str | None:
    """Türk cep numarasını wa.me biçimine çevirir: 905XXXXXXXXX.

    Sahadaki veri dağınık: `5321602442`, `0532 160 24 42`, `+90 532...`,
    `(0532) 160-2442`. Hepsi aynı numara; wa.me ülke kodlu ve yalnız rakam
    ister. Cep olmayan / tanınmayan numaralarda None döner — yanlış numaraya
    mesaj açmaktansa düğmeyi hiç göstermemek doğru.
    """
    if not ham:
        return None
    r = re.sub(r"\D", "", str(ham))
    if r.startswith("0090"):
        r = r[4:]
    elif r.startswith("90") and len(r) == 12:
        r = r[2:]
    elif r.startswith("0") and len(r) == 11:
        r = r[1:]
    # Bu noktada 10 hane ve 5 ile başlamalı (TR cep)
    if len(r) == 10 and r.startswith("5"):
        return "90" + r
    return None


def siparis_telefonu(order: Order) -> str | None:
    """Siparişin ham verisinden normalleştirilmiş cep numarası."""
    # İlk CEP numarası: müşteri kaydında sabit hat, adreste cep olabiliyor.
    from app.services.approvals import _telefon_adaylari

    for aday in _telefon_adaylari(order):
        tel = telefon_normalize(aday)
        if tel:
            return tel
    return None


# ─── Bağlantı ─────────────────────────────────────────────────────────────
def link(token: str) -> str:
    base = get_settings().support_public_base_url.rstrip("/")
    return f"{base}/model-degisim/{token}"


def talep_olustur(db: Session, order: Order, line_item, *, urun_adi: str,
                  model: str | None, mold_variation: str | None) -> ModelDegisimTalebi:
    """Yeni (ya da hâlâ geçerli olan mevcut) talebi döndürür.

    Aynı kalem için arka arkaya iki mesaj gönderilirse İKİ ayrı bağlantı
    üretmiyoruz: müşteride iki link olur, biri "geçersiz" der ve güven kırılır.
    """
    simdi = datetime.now(UTC)
    mevcut = next(
        (t for t in db.query(ModelDegisimTalebi).filter(
            ModelDegisimTalebi.order_id == order.id,
            ModelDegisimTalebi.line_item_id == (line_item.id if line_item is not None else None),
            ModelDegisimTalebi.durum == "bekliyor",
        ).all() if t.expires_at and t.expires_at > simdi),
        None,
    )
    if mevcut:
        # Operatör mesajı TEKRAR gönderiyorsa süre baştan başlar: müşteriye
        # "12 saat geçerli" diyen bir mesaj, 11 saatlik kalıntı süreyle
        # gitmemeli. Token AYNI kalır — daha önce gönderilmiş bağlantı da
        # çalışmaya devam eder.
        mevcut.expires_at = simdi + timedelta(hours=GECERLILIK_SAAT)
        db.flush()
        return mevcut

    t = ModelDegisimTalebi(
        tenant_id=order.tenant_id,
        order_id=order.id,
        line_item_id=(line_item.id if line_item is not None else None),
        token=secrets.token_urlsafe(24),
        kalip_turu=kalip_turu(mold_variation),
        urun_adi=(urun_adi or "")[:300] or None,
        mevcut_model=(model or "")[:100] or None,
        durum="bekliyor",
        expires_at=simdi + timedelta(hours=GECERLILIK_SAAT),
    )
    db.add(t)
    db.flush()
    return t


# ─── Mesaj ────────────────────────────────────────────────────────────────
def mesaj(order: Order, *, urun_adi: str, model: str, baglanti: str, tur: str) -> str:
    """Müşteriye gönderilmeye hazır WhatsApp metni.

    Metinler işletmenin verdiği şablonlardır; seçenek cümlesi kalıp türüne göre
    değişir (bkz. modül başlığı).
    """
    ad = (order.customer_name or "").strip().split(" ")[0]
    merhaba = f"Merhaba {ad}," if ad else "Merhaba,"
    kuyruk = (
        f"Tercihiniz doğrultusunda işlem yapmak için aşağıdaki linki kullanabilirsiniz: "
        f"{baglanti} Link'in geçerliliği {GECERLILIK_SAAT} saat sürecektir ve sonrasında "
        f"link geçerliliğini yitirecektir. Beklemek isterseniz bu mesaja cevap vermeyiniz "
        f"ve linkte herhangi bir işlem yapmayınız."
    )

    if tur == PARLAK:
        return (
            f"{merhaba} bu bir otomatik mesajdır. Size telefon kılıfı siparişinizdeki "
            f"{urun_adi} ile ilgili ulaşıyorum. {model} için vermiş olduğunuz sipariş "
            f"maalesef BERNZ Special'daki eksik stok nedeniyle henüz işleme alınamamıştır. "
            f"en kısa sürede tedariğini çözmek için uğraşıyoruz fakat dilerseniz telefon "
            f"modelinizi değiştirebilirsiniz veya siparişinizi şeffaf ya da standart "
            f"baskılı ürünlerimizden biri ile değiştirebilirsiniz. {kuyruk}"
        )
    if tur == SEFFAF:
        return (
            f"{merhaba} bu bir otomatik mesajdır. Size telefon kılıfı siparişinizdeki "
            f"{urun_adi} ile ilgili ulaşıyorum. {model} için vermiş olduğunuz sipariş "
            f"maalesef Şeffaf kılıflardaki eksik stok nedeniyle henüz işleme alınamamıştır. "
            f"en kısa sürede tedariğini çözmek için uğraşıyoruz fakat dilerseniz telefon "
            f"modelinizi değiştirebilir veya siparişinizi standart baskılı ürünlerimizden "
            f"biri ile değiştirebilirsiniz. {kuyruk}"
        )
    return (
        f"{merhaba} bu bir otomatik mesajdır. Size telefon kılıfı siparişiniz ile ilgili "
        f"ulaşıyorum. {model} için vermiş olduğunuz sipariş maalesef eksik stok nedeniyle "
        f"henüz işleme alınamamıştır. en kısa sürede tedariğini çözmek için uğraşıyoruz "
        f"fakat dilerseniz telefon modeli değişikliği yapabilirsiniz. {kuyruk}"
    )


def wa_url(telefon90: str, metin: str) -> str:
    """wa.me tıkla-konuş adresi. Metin URL'ye gömülür, WhatsApp hazır açar."""
    return f"https://wa.me/{telefon90}?text={quote(metin)}"


# ─── Müşteriye sunulacak varyasyonlar ────────────────────────────────────
def secilebilir_varyasyonlar(tur: str) -> list[str]:
    """Kalıp türüne göre müşterinin geçebileceği varyasyonlar.

    Ürün ağacı ileride detaylandırılacak; şimdilik kalıp varyasyonlarıyla
    aynı sözlük kullanılıyor (bkz. mold_planner). Boş liste = varyasyon
    değişikliği YOK, yalnız model.
    """
    if tur == PARLAK:
        return ["ŞEFFAF", "SİYAH", "BEYAZ"]
    if tur == SEFFAF:
        return ["SİYAH", "BEYAZ"]
    return []
