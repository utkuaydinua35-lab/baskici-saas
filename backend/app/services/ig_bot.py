"""Instagram DM otomasyonu — KURAL TABANLI (AI yok).

Sistemi bilen bir temsilcinin vereceği cevapları verir:
  1. Sipariş durumu  — "siparişim nerede? 11429" → panelden durum + kargo takip no
  2. Model uyumu     — "iPhone 16 Pro Max var mı?" → model kataloğundan var/yok
  3. Sık sorulanlar  — panelden düzenlenen anahtar kelime → hazır cevap
  4. Eşleşme yoksa   — "temsilciye aktarıldı" + panelde destek talebi

Cevap üretimi TAMAMEN yereldir (dış AI çağrısı yok) — hızlı, ücretsiz, öngörülebilir.
"""
from __future__ import annotations

import logging
import re

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import Order, Store
from app.stages import stage_info

logger = logging.getLogger("ig_bot")

# Panelden düzenlenene kadar geçerli varsayılan SSS kuralları.
# store.config["ig_faq"] = [{"keywords": [...], "reply": "..."}] ile ezilir.
DEFAULT_FAQ = [
    {"keywords": ["kargo ne zaman", "ne zaman kargo", "kaç günde", "kac gunde", "teslimat süresi", "teslimat suresi"],
     "reply": "Siparişler kişiye özel üretildiği için ortalama 1-3 iş günü içinde kargoya veriliyor. "
              "Kargoya verildiğinde takip numarası e-postanıza gönderilir 📦"},
    {"keywords": ["fiyat", "ne kadar", "kaç para", "kac para", "ücret", "ucret"],
     "reply": "Fiyatlarımız modele ve tasarıma göre değişiyor. Sitemizden güncel fiyatları görebilir, "
              "istediğiniz modeli yazarsanız size özel bilgi verebiliriz 💬"},
    {"keywords": ["iade", "değişim", "degisim", "cayma"],
     "reply": "Ürünlerimiz siparişe özel üretildiği için (6502 sayılı kanun md.15) cayma hakkı kapsamında "
              "iade alınmıyor. Ancak üretim ya da kargo kaynaklı bir sorun olursa ürünü ücretsiz yeniliyoruz 🙏"},
    {"keywords": ["kişiye özel", "kisiye ozel", "özel tasarım", "ozel tasarim", "kendi tasarımım", "kendi tasarimim"],
     "reply": "Evet! Kendi fotoğrafınızı veya tasarımınızı kılıfa basabiliyoruz 🎨 "
              "Telefon modelinizi ve görselinizi paylaşırsanız hemen ilerleyelim."},
    {"keywords": ["merhaba", "selam", "iyi günler", "iyi gunler", "hey"],
     "reply": "Merhaba! 👋 Size nasıl yardımcı olabilirim? Sipariş durumunuzu öğrenmek için sipariş "
              "numaranızı yazabilirsiniz."},
]

_ORDER_RE = re.compile(r"#?\b(\d{4,8})\b")
_EMAIL_RE = re.compile(r"[\w.\-+]+@[\w\-]+\.[\w.\-]+")
_ORDER_HINT = re.compile(
    r"sipari[şs]|kargo|takip|nerede|ne zaman gelir|geldi mi|durum", re.I)
_MODEL_HINT = re.compile(
    r"var m[ıi]|uygun mu|modeli|model[iı]m|için var|icin var|yap[ıi]yor musunuz", re.I)


def _norm(s: str) -> str:
    return (s or "").strip().lower()


# ─── 1) Sipariş durumu ───────────────────────────────────────
def _find_order(db: Session, tenant_id, text: str) -> Order | None:
    """Mesajdaki sipariş numarası ya da e-posta ile siparişi bul."""
    email = _EMAIL_RE.search(text or "")
    if email:
        o = db.scalar(
            select(Order).where(Order.tenant_id == tenant_id,
                                Order.customer_email.ilike(email.group(0)))
            .order_by(desc(Order.created_at)).limit(1))
        if o:
            return o
    for m in _ORDER_RE.finditer(text or ""):
        num = m.group(1)
        o = db.scalar(
            select(Order).where(Order.tenant_id == tenant_id, Order.order_number == num)
            .order_by(desc(Order.created_at)).limit(1))
        if o:
            return o
    return None


def _tracking_of(order: Order) -> tuple[str | None, str | None]:
    """(takip_no, kargo_firması) — kargo bilgisi varsa."""
    ki = getattr(order, "kargo_info", None) or {}
    if isinstance(ki, dict):
        return (ki.get("takip_no") or None, ki.get("handler_name") or None)
    return (None, None)


def order_status_reply(db: Session, tenant_id, text: str) -> str | None:
    order = _find_order(db, tenant_id, text)
    if not order:
        return None
    if getattr(order, "is_iptal", False) or order.cancelled_at:
        return f"#{order.order_number} numaralı siparişiniz iptal edilmiş görünüyor. " \
               f"Yanlışlık olduğunu düşünüyorsanız yazın, kontrol edelim."
    takip, firma = _tracking_of(order)
    if takip:
        return (f"#{order.order_number} numaralı siparişiniz kargoya verildi 🚚\n"
                f"{firma or 'Kargo'} takip numarası: {takip}\n"
                f"Kargo firmasının sitesinden takip edebilirsiniz.")
    st = stage_info(order.current_stage or 0)
    label = (st or {}).get("label") or "hazırlanıyor"
    return (f"#{order.order_number} numaralı siparişiniz şu anda: {label} ⏳\n"
            f"Kargoya verildiğinde takip numarasını paylaşacağız.")


# ─── 2) Telefon modeli uyumu ─────────────────────────────────
def model_reply(db: Session, tenant_id, text: str) -> str | None:
    """Mesajda geçen telefon modelini sistem kataloğunda ara."""
    from app.services import phone_models as pm
    t = (text or "").strip()
    if len(t) < 3:
        return None
    # Mesajdaki en uzun anlamlı parçayı model olarak dene (ör "iphone 16 pro max")
    cand = re.sub(r"[?!.,;:]", " ", t)
    cand = re.sub(r"\b(var|m[ıi]|mi|uygun|mu|modeli|model|i[çc]in|yap[ıi]yor|musunuz|k[ıi]l[ıi]f[ıi]?|telefon)\b",
                  " ", cand, flags=re.I)
    cand = " ".join(cand.split())
    if not cand:
        return None
    try:
        spec = pm.get_spec(db, tenant_id, cand)
    except Exception:  # noqa: BLE001
        spec = None
    if not spec:
        return None
    disp = pm.canonical_model_name(pm.normalize_key(cand)) or cand
    return (f"Evet, {disp} için kılıfımız var ✅\n"
            f"Siyah, beyaz, şeffaf ve parlak seçenekleriyle üretebiliyoruz. "
            f"Hangi tasarımı istediğinizi yazarsanız hemen ilerleyelim 🎨")


# ─── 3) Sık sorulanlar (panelden düzenlenebilir) ─────────────
def faq_rules(store: Store | None) -> list[dict]:
    cfg = (getattr(store, "config", None) or {}) if store else {}
    rules = cfg.get("ig_faq")
    if isinstance(rules, list) and rules:
        return [r for r in rules if isinstance(r, dict) and r.get("reply")]
    return DEFAULT_FAQ


def faq_reply(store: Store | None, text: str) -> str | None:
    t = _norm(text)
    if not t:
        return None
    for rule in faq_rules(store):
        for kw in (rule.get("keywords") or []):
            k = _norm(kw)
            if k and k in t:
                return rule["reply"]
    return None


# ─── Ana giriş ───────────────────────────────────────────────
FALLBACK = ("Mesajınızı aldık, teşekkürler! 🙏 Bir temsilcimiz en kısa sürede size dönecek. "
            "Sipariş durumu için sipariş numaranızı yazabilirsiniz.")


def build_reply(db: Session, tenant_id, store: Store | None, text: str) -> tuple[str, str]:
    """Gelen mesaja kural tabanlı yanıt üret.
    Döner: (yanıt_metni, kural_adı). kural_adı='fallback' ise temsilciye aktarılmalı."""
    t = (text or "").strip()
    if not t:
        return FALLBACK, "fallback"

    # 1) Sipariş: numara/e-posta varsa ya da sipariş sorusu gibi görünüyorsa
    if _ORDER_RE.search(t) or _EMAIL_RE.search(t) or _ORDER_HINT.search(t):
        r = order_status_reply(db, tenant_id, t)
        if r:
            return r, "order_status"
        if _ORDER_HINT.search(t) and not _MODEL_HINT.search(t):
            return ("Sipariş numaranızı (ör. 11429) ya da sipariş verirken kullandığınız e-posta "
                    "adresinizi yazarsanız durumu hemen kontrol edeyim 🔎"), "order_ask"

    # 2) Model uyumu
    if _MODEL_HINT.search(t) or re.search(r"iphone|samsung|xiaomi|redmi|galaxy|poco|huawei|oppo|realme|honor", t, re.I):
        r = model_reply(db, tenant_id, t)
        if r:
            return r, "model_ok"
        if _MODEL_HINT.search(t):
            return ("Telefon modelinizi tam olarak yazar mısınız? (ör. iPhone 16 Pro Max, "
                    "Samsung Galaxy S24) Hemen kontrol edeyim 📱"), "model_ask"

    # 3) SSS
    r = faq_reply(store, t)
    if r:
        return r, "faq"

    # 4) Devret
    return FALLBACK, "fallback"
