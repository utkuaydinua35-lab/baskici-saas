"""Müşteri tasarım onayı — servis katmanı.

Onay kaydı oluşturma, görsel/telefon/mesaj çözümleme, public payload.
Token'lı public sayfa (siparistakip/onay/{token}) üzerinden müşteri onaylar.
"""
from __future__ import annotations

import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import DesignApproval, KisiyeOzelProduct, Order

STATUS_LABELS = {
    "bekliyor": "Onay bekliyor",
    "onaylandi": "Onaylandı",
    "revizyon": "Revizyon istendi",
}

# Müşterinin sipariş başına en fazla revizyon isteme hakkı
MAX_REVISIONS = 1


def revisions_used(db: Session, order_id) -> int:
    """Bu sipariş için müşterinin şimdiye kadar istediği revizyon sayısı."""
    from sqlalchemy import func as _f
    return db.scalar(
        select(_f.count(DesignApproval.id)).where(
            DesignApproval.order_id == order_id,
            DesignApproval.status == "revizyon",
        )
    ) or 0


def resolve_phone(order: Order) -> str | None:
    """Sipariş ham verisinden müşteri telefonu (Shopify customer/shipping)."""
    raw = order.raw or {}
    cust = raw.get("customer") or {}
    ship = raw.get("shipping_address") or {}
    for c in (cust.get("phone"), ship.get("phone"), raw.get("phone")):
        if c and str(c).strip():
            return str(c).strip()
    return None


def _absolute(url: str | None) -> str | None:
    """/storage/... göreli yolu, public erişim için panel domain'iyle mutlak yap."""
    if not url:
        return None
    if url.startswith("http"):
        return url
    base = get_settings().panel_base_url.rstrip("/")
    return f"{base}{url}"


def _variation_of(li) -> str:
    """Kılıf varyasyonu (mockup için): şeffaf mı siyah mı."""
    text = " ".join(filter(None, [
        getattr(li, "birincil_renk", None),
        getattr(li, "variant_title", None),
        getattr(li, "title", None),
    ])).lower()
    if any(k in text for k in ["şeffaf", "seffaf", "şefaf", "transparent", "clear", "silikon"]):
        return "seffaf"
    return "siyah"


def _resolve_phone_model(db, tenant_id, li):
    """Kalemin telefon modelini çöz (mockup şablonu için). Bulunamazsa None."""
    from app.services import phone_models as pmsvc
    model_str = (getattr(li, "device_model_override", None)
                 or getattr(li, "variant_title", None) or "")
    if not model_str:
        return None
    try:
        return pmsvc._db_lookup(db, tenant_id, pmsvc.normalize_key(model_str))
    except Exception:  # noqa: BLE001
        return None


def build_items(db: Session, order: Order) -> list[dict]:
    """Müşteriye gösterilecek tasarımlar — YALNIZCA kişiye özel kalemler.
    Tasarım (PDF) kılıf mockup'ına oturtulup numune görseli üretilir; mockup
    başarısız olursa PDF thumbnail'ına düşülür. Ürünün katalog görseli DEĞİL.
    Tasarımı yüklenmemiş kalemler atlanır.
    """
    from app.services import storage, mockup

    # Bu store'un kişiye özel product_id'leri
    pids = set(db.scalars(
        select(KisiyeOzelProduct.product_id).where(KisiyeOzelProduct.store_id == order.store_id)
    ).all())

    items = []
    for li in (order.line_items or []):
        # sadece kişiye özel kalemler
        if not (li.product_id and str(li.product_id) in pids):
            continue
        d = li.assigned_design
        # tasarım (PDF) yüklenmemişse onaya dahil etme
        if not (li.assigned_design_id and d and getattr(d, "file_path", None)):
            continue

        variation = _variation_of(li)
        pm = _resolve_phone_model(db, order.tenant_id, li)
        # Numune mockup üret (model şablonu varsa gerçek foto, yoksa çizim); olmazsa thumbnail
        mock_url = mockup.generate_mockup_url(d, order.tenant_id, variation, phone_model=pm)
        preview = mock_url or storage.get_thumbnail_url(d.file_path, d.file_format)

        items.append({
            "image_url": _absolute(preview),
            "file_url": _absolute(storage.get_design_url(d.file_path)),
            "file_format": getattr(d, "file_format", None),
            "title": li.title or "Ürün",
            "quantity": getattr(li, "quantity", 1) or 1,
            "is_mockup": bool(mock_url),
        })
    return items


def approval_link(token: str) -> str:
    base = get_settings().support_public_base_url.rstrip("/")
    return f"{base}/onay/{token}"


def build_message(order: Order, link: str) -> str:
    """Müşteriye gönderilmeye hazır mesaj (operatör elle WhatsApp/Instagram'dan yollar)."""
    ad = (order.customer_name or "").split()[0] if order.customer_name else ""
    no = order.name or f"#{order.order_number}"
    merhaba = f"Merhaba {ad}," if ad else "Merhaba,"
    return (
        f"{merhaba}\n\n{no} numaralı siparişinizin tasarımını hazırladık. "
        f"Lütfen aşağıdaki linkten inceleyip onaylar mısınız?\n\n{link}\n\n"
        f"Onayınızın ardından baskıya alıyoruz. Teşekkürler!"
    )


class NoApprovalItems(Exception):
    """Onaya gönderilecek (tasarımı yüklenmiş) kişiye özel kalem yok."""


def create_approval(db: Session, order: Order, user, note: str | None = None) -> DesignApproval:
    """Sipariş için yeni onay kaydı (versiyon = mevcut max + 1).

    Tasarımı yüklenmiş kişiye özel kalem yoksa NoApprovalItems yükseltir.
    """
    items = build_items(db, order)
    if not items:
        raise NoApprovalItems(
            "Onaya gönderilecek kişiye özel tasarım bulunamadı. "
            "Önce kişiye özel kalem(ler)in tasarım dosyasını (PDF) yükleyin."
        )
    existing = order.approvals or []
    version = max((a.version for a in existing), default=0) + 1
    token = secrets.token_urlsafe(24)
    ap = DesignApproval(
        tenant_id=order.tenant_id, order_id=order.id, token=token,
        status="bekliyor", version=version, items=items,
        note=(note or None),
        created_by=(getattr(user, "full_name", None) or getattr(user, "email", None)) if user else None,
    )
    db.add(ap)
    db.flush()
    return ap


def serialize(ap: DesignApproval, with_secrets: bool = False) -> dict:
    d = {
        "id": str(ap.id),
        "status": ap.status,
        "status_label": STATUS_LABELS.get(ap.status, ap.status),
        "version": ap.version,
        "items": ap.items or [],
        "note": ap.note,
        "customer_note": ap.customer_note,
        "decided_at": ap.decided_at.isoformat() if ap.decided_at else None,
        "created_by": ap.created_by,
        "created_at": ap.created_at.isoformat() if ap.created_at else None,
    }
    if with_secrets:
        d["token"] = ap.token
        d["link"] = approval_link(ap.token)
    return d


def public_payload(ap: DesignApproval, order: Order) -> dict:
    """Public onay sayfası için — hassas veri (email/telefon/adres) YOK."""
    return {
        "order_no": order.name or f"#{order.order_number}",
        "atolye": None,  # router dolduracak (tenant adı)
        "status": ap.status,
        "status_label": STATUS_LABELS.get(ap.status, ap.status),
        "version": ap.version,
        "items": [
            {
                "image_url": it.get("image_url"),
                "file_url": it.get("file_url"),
                "file_format": it.get("file_format"),
                "title": it.get("title"),
                "quantity": it.get("quantity", 1),
                "is_mockup": it.get("is_mockup", False),
            }
            for it in (ap.items or [])
        ],
        "note": ap.note,
        "customer_note": ap.customer_note,
        "decided_at": ap.decided_at.isoformat() if ap.decided_at else None,
    }
