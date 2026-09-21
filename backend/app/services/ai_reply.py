"""AI destek yanıtı — Claude API ile müşteri destek mesajlarına taslak cevap.

Operatör taslağı görür, düzenler ve gönderir (otomatik gönderilmez).
ANTHROPIC_API_KEY .env'de yoksa özellik sessizce kapalıdır (DraftError döner).
"""
from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models import (
    KisiyeOzelProduct,
    LineItem,
    Order,
    SupportMessage,
    SupportThread,
    Tenant,
)

logger = logging.getLogger("ai_reply")

# Kullanici secimi -> gercek model ID (settings'te haiku|sonnet|opus tutulur)
MODEL_MAP = {
    "haiku": "claude-haiku-4-5",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-8",
}
DEFAULT_MODEL_KEY = "opus"
MAX_TOKENS = 1024
# Çok uzun konuşmalarda son N mesaj yeterli (taslak için bağlam)
MAX_HISTORY = 30

# ESKİ SABİT TESLİM BİLGİSİ — artık KULLANILMIYOR, yalnız migration'ın
# mevcut mağazalara tohumladığı metnin kaynağı olarak duruyor. Teslim bilgisi
# her mağazanın kendi ayarından okunur (store.config["ai_teslim_bilgisi"]).
_DELIVERY_INFO = """BERNZ TESLİM SÜRELERİ (iş günü; Cumartesi/Pazar hariç. Tahmini \
sürelerdir, toptancı yoğunluğuna göre değişebilir):
- iPhone modelleri (normal kılıf): ortalama 7 iş günü içinde kargoya verilir.
- Parlak, Şeffaf ve MagSafe kılıflar: ortalama 10–14 iş günü.
- Android modeller: ortalama 10–14 iş günü.
- Kişiye özel tasarımlar: ortalama 10–15 iş günü, azami 30 iş günü (tasarım sırasına bağlı).
- Android, MagSafe ve Parlak kılıflar talep üzerine tedarik edilir; BERNZ azami 30 iş \
gününe kadar bekletme hakkını saklı tutar.
Karışık siparişte teslim süresi, en uzun süreli kaleme göre belirlenir. Kesin gün/tarih \
verme; "ortalama", "tahmini" ve aralık (ör. 10–14 iş günü) ifadeleri kullan."""


# Kişilik başlığı konuşmanın MAĞAZASINDAN kurulur (bkz. _sistem_promptu).
# Eskiden "Sen BERNZ adlı telefon kılıfı baskı atölyesinin…" sabitti: 505 Cover
# ve Lunera müşterilerine de BERNZ adıyla yazılıyordu; sistem kiralandığında
# ise başka bir işletmenin müşterisine BERNZ olarak cevap verilecekti.
_SYSTEM = """Müşterinin son mesajı için İKİ şey üretirsin: bir yanıt \
taslağı (draft) ve operatöre kısa bir not (note).

DRAFT (müşteriye gönderilmeye hazır yanıt):
- KARARLI ve NET ol. Tereddüt etme; operatöre ya da müşteriye gereksiz soru sorma.
- Doğrudan, çözüm odaklı, sıcak ve profesyonel; kısa tut.
- ASLA uydurma bilgi verme: kesin kargo tarihi, takip numarası, iade onayı, \
indirim gibi emin olmadığın şeyleri uydurma. Gerekiyorsa "[kargo tarihi]" gibi \
köşeli parantezli yer tutucu bırak; operatör doldurur.
- İmza veya "... Destek" gibi kapanış ekleme; sadece mesaj gövdesi.

TESLİM SÜRESİ / "ne zaman gelir" SORULARI:
- Müşteri teslim/kargo süresi sorarsa, aşağıdaki "TESLİM SÜRELERİ" \
kurallarını ve (varsa) "SİPARİŞ İÇERİĞİ" analizini kullanarak siparişe ÖZEL yanıt ver.
- Siparişteki kalemlere göre doğru kategoriyi seç: iPhone normal mi, Android mı, \
özel kılıf (parlak/şeffaf/magsafe) mı, kişiye özel mi. Karışıksa en uzun süreliye göre söyle.
- Kişiye özel ve tasarım onayı BEKLİYORSA: önce tasarım onayının alınması gerektiğini, \
sürenin onaydan sonra işlemeye başlayacağını nazikçe belirt.
- Kişiye özel ve onay ALINMIŞSA: üretim sırasına göre süreyi ver.
- Kesin gün/tarih uydurma; aralık + "tahmini/ortalama" kullan.

NOTE (yalnızca operatöre, müşteriye GÖSTERİLMEZ):
- draft içinde operatörün doldurması gereken yer tutucuları ve karar vermesi \
gereken konuları kısa madde madde özetle (ör. "• [kargo tarihi] doldur  • \
İade onayı verilecek mi karar ver").
- Doldurulacak veya karar verilecek bir şey yoksa boş string ("") döndür.

Her ikisini de yalnızca Türkçe yaz."""

# Yapılandırılmış çıktı şeması (draft + note garantili JSON)
_FORMAT = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "draft": {"type": "string"},
            "note": {"type": "string"},
        },
        "required": ["draft", "note"],
        "additionalProperties": False,
    },
}


class DraftError(Exception):
    """AI taslak üretilemedi (anahtar yok, API hatası vb.)."""


def _history_messages(db: Session, thread: SupportThread) -> list[dict]:
    rows = db.scalars(
        select(SupportMessage)
        .where(SupportMessage.thread_id == thread.id)
        .order_by(SupportMessage.created_at.asc())
    ).all()
    rows = rows[-MAX_HISTORY:]

    messages: list[dict] = []
    for m in rows:
        role = "user" if m.sender == "musteri" else "assistant"
        text = (m.body or "").strip()
        if m.image_url:
            note = "[müşteri bir görsel ekledi]" if m.sender == "musteri" else "[görsel eklendi]"
            text = f"{text}\n{note}".strip()
        if not text:
            continue
        messages.append({"role": role, "content": text})

    # Claude'un ilk mesajı 'user' olmalı; baştaki admin mesajlarını at
    while messages and messages[0]["role"] != "user":
        messages.pop(0)
    return messages


def _find_order(db: Session, tenant_id, thread: SupportThread):
    opts = (
        selectinload(Order.line_items).selectinload(LineItem.assigned_design),
        selectinload(Order.approvals),
    )
    order = None
    if thread.order_number:
        order = db.scalar(
            select(Order).where(
                Order.tenant_id == tenant_id, Order.order_number == str(thread.order_number)
            ).options(*opts)
        )
    if not order and thread.shopify_order_id:
        order = db.scalar(
            select(Order).where(
                Order.tenant_id == tenant_id, Order.external_id == str(thread.shopify_order_id)
            ).options(*opts)
        )
    return order


def _analyze_order(db: Session, tenant_id, thread: SupportThread) -> str | None:
    """Siparişin model/kılıf/kişiye-özel/onay analizini AI bağlamı olarak üret."""
    from app.services import placement_rules as pr

    order = _find_order(db, tenant_id, thread)
    if not order or not order.line_items:
        return None

    kop_ids = set(db.scalars(
        select(KisiyeOzelProduct.product_id).where(KisiyeOzelProduct.store_id == order.store_id)
    ).all())
    approval_status = order.approvals[0].status if getattr(order, "approvals", None) else None

    lines = []
    for li in order.line_items:
        model = (getattr(li, "device_model_override", None)
                 or li.variant_title or li.title or "Ürün")
        grp = pr.get_model_group(model)
        is_unknown = grp in ("UNKNOWN-GROUP", "IPHONE-UNKNOWN")
        is_iphone = grp.startswith("IPHONE")
        design = getattr(li, "assigned_design", None)
        var = pr.normalize_variation(getattr(design, "kalip_tipi", None)) if design else None
        special = var in ("PARLAK", "ŞEFFAF", "MAGSAFE")
        ko = bool(li.product_id and str(li.product_id) in kop_ids)

        tags = []
        if not is_unknown:
            tags.append("iPhone modeli" if is_iphone else "Android modeli")
        if special:
            # ⚠ .capitalize() Türkçe'de bozuk ("SİYAH" → "Si̇yah")
            from app.services.tr_metin import baslik as _tr
            tags.append(f"{_tr(var)} kılıf")
        if ko:
            tags.append("kişiye özel tasarım")
        lines.append(f"- {model}" + (f" ({', '.join(tags)})" if tags else ""))

    txt = f"SİPARİŞ İÇERİĞİ (#{order.order_number}):\n" + "\n".join(lines)
    if approval_status:
        lbl = {"bekliyor": "onay BEKLİYOR", "onaylandi": "onaylandı",
               "revizyon": "revizyon istendi"}.get(approval_status, approval_status)
        txt += f"\nKişiye özel tasarım onay durumu: {lbl}."
    return txt


def _sistem_promptu(db: Session, thread: SupportThread, tenant) -> str:
    """Kişilik + teslim kuralları — konuşmanın MAĞAZASINA göre."""
    from app.models import Store

    store = db.get(Store, thread.store_id) if thread.store_id else None
    config = (store.config or {}) if store else {}
    ad = ((store.name if store else None)
          or getattr(tenant, "app_name", None) or getattr(tenant, "name", None)
          or "mağaza").strip()
    tur = (config.get("isletme_urun_turu") or "").strip()
    kimlik = (f"Sen {ad} adlı işletmenin Türkçe müşteri destek temsilcisisin."
              + (f" İşletme {tur} satıyor." if tur else ""))

    teslim = (config.get("ai_teslim_bilgisi") or "").strip()
    if not teslim:
        kisa = (config.get("isletme_teslim_suresi") or "").strip()
        teslim = (f"TESLİM SÜRESİ: siparişler ortalama {kisa} içinde kargoya verilir. "
                  "Kesin gün/tarih verme; 'ortalama', 'tahmini' ifadelerini kullan."
                  if kisa else
                  "TESLİM SÜRESİ: bu işletme için tanımlı bir teslim süresi YOK. "
                  "Süre sorulursa ASLA uydurma; draft'a [teslim süresi] yer tutucusu "
                  "bırak ve note'ta operatöre doldurmasını söyle.")
    return f"{kimlik} {_SYSTEM}\n\n{teslim}"


def draft_reply(db: Session, thread: SupportThread) -> dict:
    """Konuşma geçmişinden {draft, note} üret. Hata olursa DraftError.

    draft: müşteriye gönderilmeye hazır yanıt.
    note:  operatöre kısa not (doldurulacak/karar verilecek konular; yoksa "").
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise DraftError("AI taslak özelliği yapılandırılmamış (ANTHROPIC_API_KEY yok).")

    # Tenant ayari: AI acik mi + hangi model
    tenant = db.get(Tenant, thread.tenant_id) if thread.tenant_id else None
    if tenant is not None and not tenant.ai_reply_enabled:
        raise DraftError("AI yanıt özelliği kapalı. Ayarlar > AI Destek'ten açın.")
    model_key = (getattr(tenant, "ai_reply_model", None) or DEFAULT_MODEL_KEY)
    model = MODEL_MAP.get(model_key, MODEL_MAP[DEFAULT_MODEL_KEY])

    history = _history_messages(db, thread)
    if not history:
        raise DraftError("Taslak için müşteri mesajı bulunamadı.")

    try:
        import anthropic
    except ModuleNotFoundError as e:
        raise DraftError("anthropic SDK kurulu değil.") from e

    # Sistem promptu = kişilik + teslim süresi kuralları (mağazaya göre)
    system = _sistem_promptu(db, thread, tenant)

    # Sipariş bağlamı (no/müşteri + içerik analizi)
    ctx_parts = []
    if thread.order_number:
        ctx_parts.append(f"Sipariş no: {thread.order_number}")
    if thread.customer_name:
        ctx_parts.append(f"Müşteri: {thread.customer_name}")
    if ctx_parts:
        system += f"\n\nBAĞLAM: {' · '.join(ctx_parts)}"
    try:
        analiz = _analyze_order(db, thread.tenant_id, thread)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[ai_reply] sipariş analizi hata: {e}")
        analiz = None
    if analiz:
        system += f"\n\n{analiz}"

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        # Yapılandırılmış çıktı: {draft, note}. effort yalnizca opus/sonnet'te
        # desteklenir (haiku'da 400 verir) — format ile birlikte gonderiyoruz.
        output_config = {"format": _FORMAT}
        if model_key in ("opus", "sonnet"):
            output_config["effort"] = "low"
        resp = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=history,
            output_config=output_config,
        )
    except anthropic.APIError as e:
        logger.warning(f"[ai_reply] API hatası: {e}")
        raise DraftError("AI servisi şu anda yanıt veremedi, lütfen tekrar deneyin.") from e
    except Exception as e:  # noqa: BLE001
        logger.exception(f"[ai_reply] beklenmeyen hata: {e}")
        raise DraftError("Taslak üretilirken bir hata oluştu.") from e

    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
    if not text:
        raise DraftError("AI boş bir taslak döndürdü, lütfen tekrar deneyin.")

    # output_config.format JSON garantiler; yine de güvenli parse + fallback
    try:
        data = json.loads(text)
        draft = (data.get("draft") or "").strip()
        note = (data.get("note") or "").strip()
    except (json.JSONDecodeError, AttributeError):
        draft, note = text, ""

    if not draft:
        raise DraftError("AI boş bir taslak döndürdü, lütfen tekrar deneyin.")
    return {"draft": draft, "note": note}
