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


def _telefon_adaylari(order: Order) -> list[str]:
    raw = order.raw or {}
    cust = raw.get("customer") or {}
    ship = raw.get("shipping_address") or {}
    bill = raw.get("billing_address") or {}
    # customer_phone: bayi / telafi / elle açılan siparişler telefonu burada tutuyor
    return [str(c).strip() for c in (cust.get("phone"), ship.get("phone"), raw.get("phone"),
                                     raw.get("customer_phone"), bill.get("phone"))
            if c and str(c).strip()]


def resolve_phone(order: Order) -> str | None:
    """Sipariş ham verisinden müşteri telefonu (Shopify customer/shipping)."""
    aday = _telefon_adaylari(order)
    return aday[0] if aday else None


def wa_url(order: Order, metin: str | None) -> str | None:
    """Hazır mesajla WhatsApp (wa.me) adresi — cep numarası yoksa None.

    Adaylardan ilk CEP numarası seçilir: müşteri kaydında sabit hat, teslimat
    adresinde cep numarası olabiliyor; ilkini körü körüne almak WhatsApp'ı
    açılmayan bir numaraya yönlendiriyordu.
    """
    if not metin:
        return None
    from app.services import model_degisim as md
    for aday in _telefon_adaylari(order):
        tel = md.telefon_normalize(aday)
        if tel:
            return md.wa_url(tel, metin)
    return None


def _absolute(url: str | None) -> str | None:
    """/storage/... göreli yolu, public erişim için panel domain'iyle mutlak yap."""
    if not url:
        return None
    if url.startswith("http"):
        return url
    base = get_settings().panel_base_url.rstrip("/")
    return f"{base}{url}"


def _variation_of(li, design=None, slot: int = 1) -> str:
    """Kılıf varyasyonu (mockup için) — ÜRETİMLE AYNI kaynak (mold_planner) kullanılır ki
    müşteriye gösterilen onay görseli, basılacak kılıfla aynı olsun.
    (Eskiden yalnız şeffaf/siyah ayırt ediliyordu; PARLAK/BEYAZ/MAGSAFE siyah görünüyordu.)"""
    from app.services.mold_planner import resolve_line_variation
    v = resolve_line_variation(li, design, slot=slot)
    if v:
        return v
    # Son çare: metinden şeffaf ipucu (mockup varsayılanı siyah)
    text = " ".join(filter(None, [
        getattr(li, "birincil_renk", None),
        getattr(li, "variant_title", None),
        getattr(li, "title", None),
    ])).lower()
    if any(k in text for k in ["şeffaf", "seffaf", "şefaf", "transparent", "clear", "silikon"]):
        return "seffaf"
    return "siyah"


def _resolve_phone_model(db, tenant_id, li):
    """Kalemin telefon modelini çöz (mockup şablonu için) — sistemin kanonik
    çıkarımıyla (properties 'Model' öncelikli). Bulunamazsa None."""
    from app.services.mold_planner import extract_phone_model
    return _resolve_phone_model_by_str(db, tenant_id, extract_phone_model(li) or "")


def _resolve_phone_model_by_str(db, tenant_id, model_str: str):
    """Açık model metninden (couple+kişiye özel slot override'ı) çöz."""
    if not model_str or not model_str.strip():
        return None
    from app.services import phone_models as pmsvc
    try:
        return pmsvc._db_lookup(db, tenant_id, pmsvc.normalize_key(model_str.strip()))
    except Exception:  # noqa: BLE001
        return None


def build_items(db: Session, order: Order) -> list[dict]:
    """Müşteriye gösterilecek tasarımlar — YALNIZCA kişiye özel kalemler.
    Tasarım (PDF) kılıf mockup'ına oturtulup numune görseli üretilir; mockup
    başarısız olursa PDF thumbnail'ına düşülür. Ürünün katalog görseli DEĞİL.
    Tasarımı yüklenmemiş kalemler atlanır.
    """
    from app.models import CoupleProduct
    from app.services import storage, mockup

    # Bu store'un kişiye özel product_id'leri
    pids = set(db.scalars(
        select(KisiyeOzelProduct.product_id).where(KisiyeOzelProduct.store_id == order.store_id)
    ).all())
    # couple + kişiye özel ürünler (2 tasarım sipariş başına yüklenir)
    couple_ko_ids = set(db.scalars(
        select(CoupleProduct.product_id).where(
            CoupleProduct.store_id == order.store_id,
            CoupleProduct.is_kisiye_ozel.is_(True),
        )
    ).all())

    def _mk_item(li, d, pm, title, qty, variation, slot: int = 1):
        mock_url = mockup.generate_mockup_url(d, order.tenant_id, variation,
                                              phone_model=pm, db=db)
        preview = mock_url or storage.get_thumbnail_url(d.file_path, d.file_format)
        return {
            # Hangi kaleme ve hangi yarıya ait: paketleme müşteriye GÖNDERİLEN
            # numuneyi gösteriyor, eşleştirmeyi başlık tahminiyle yapmasın.
            "line_item_id": str(li.id),
            "slot": slot,
            "design_id": str(d.id) if getattr(d, "id", None) else None,
            "image_url": _absolute(preview),
            "file_url": _absolute(storage.get_design_url(d.file_path)),
            "file_format": getattr(d, "file_format", None),
            "title": title,
            "quantity": qty,
            "is_mockup": bool(mock_url),
        }

    items = []
    for li in (order.line_items or []):
        pid = str(li.product_id) if li.product_id else None
        if not pid:
            continue

        # couple + kişiye özel: iki slot (1./2. kılıf) ayrı tasarım+model+varyasyon
        if pid in couple_ko_ids:
            base = li.title or "Ürün"
            slots = [
                (1, li.assigned_design, (li.device_model_override or "")),
                (2, li.assigned_design_2, (li.device_model_override_2 or "")),
            ]
            for slot, d, mstr in slots:
                if not (d and getattr(d, "file_path", None)):
                    continue
                pm = _resolve_phone_model_by_str(db, order.tenant_id, mstr) \
                    or _resolve_phone_model(db, order.tenant_id, li)
                variation = _variation_of(li, d, slot=slot)   # üretimle aynı çözüm
                items.append(_mk_item(li, d, pm, f"{base} — {slot}. kılıf", 1, variation, slot=slot))
            continue

        # tekli kişiye özel kalem
        if pid not in pids:
            continue
        d = li.assigned_design
        # tasarım (PDF) yüklenmemişse onaya dahil etme
        if not (li.assigned_design_id and d and getattr(d, "file_path", None)):
            continue
        pm = _resolve_phone_model(db, order.tenant_id, li)
        variation = _variation_of(li, d)   # üretimle aynı çözüm (elle > property > ad > tasarım)
        items.append(_mk_item(li, d, pm, li.title or "Ürün", getattr(li, "quantity", 1) or 1, variation))

    # Tasarım stüdyosu işleri: müşterinin KENDİ hazırladığı tasarım da onaya
    # gider. Görsel olarak stüdyo önizlemesi gösterilir; indirilecek dosya
    # baskıya hazır çıktıdır (siz rötuşladıktan sonra yeniden üretilebilir).
    items += _studyo_items(db, order)
    return items


def numune_gorselleri(db: Session, order: Order) -> dict:
    """{(line_item_id, slot): numune_url} — müşteriye GÖNDERİLEN numune görselleri.

    Paketleme kişiye özel ürünü kılıf üzerindeki numuneyle göstermeli: kutuya
    giren şey o. Kaynak, müşteriye gerçekten gönderilen onay kaydıdır (en yeni
    versiyon); böylece ekranda görülen ile müşterinin gördüğü AYNI olur ve
    mockup yeniden üretilmez.

    Eski kayıtlarda line_item_id yoktu — orada başlığa göre eşleştirilir; o da
    tutmazsa tek kalemli siparişte tek numune o kaleme aittir.
    """
    from app.models import DesignApproval

    aps = db.scalars(
        select(DesignApproval).where(DesignApproval.order_id == order.id)
        .order_by(DesignApproval.version.asc(), DesignApproval.created_at.asc())
    ).all()
    if not aps:
        return {}
    kalemler = list(order.line_items or [])
    basliklar = {(li.title or "").strip(): li for li in kalemler if li.title}
    out: dict = {}
    for ap in aps:                      # eskiden yeniye: en yeni versiyon üzerine yazar
        for it in (ap.items or []):
            url = it.get("image_url")
            if not url:
                continue
            lid, slot = it.get("line_item_id"), int(it.get("slot") or 1)
            if not lid:
                baslik = (it.get("title") or "").strip()
                li = basliklar.get(baslik)
                if li is None and baslik:
                    # "Ürün — 1. kılıf" gibi ekli başlıklar
                    kok = baslik.split(" — ")[0].strip()
                    li = basliklar.get(kok)
                    if li is not None and " — " in baslik and baslik.rstrip().endswith("kılıf"):
                        try:
                            slot = int(baslik.rsplit("—", 1)[1].strip().split(".")[0])
                        except (ValueError, IndexError):
                            pass
                if li is None and len(kalemler) == 1:
                    li = kalemler[0]
                if li is None:
                    continue
                lid = str(li.id)
            out[(str(lid), slot)] = url
    return out


def _studyo_items(db: Session, order: Order) -> list[dict]:
    from app.models import CustomerDesign

    ids: list[str] = []
    kalem_of: dict = {}                     # tasarım no -> kalem (paketleme eşlemesi)
    for li in (order.line_items or []):
        for prop in (li.properties or []):
            if prop.get("name") == "Tasarım No" and prop.get("value"):
                ids.append(str(prop["value"]))
                kalem_of.setdefault(str(prop["value"]), li)
    if not ids:
        return []

    out = []
    for did in dict.fromkeys(ids):          # sırayı koru, tekrarı at
        try:
            d = db.scalar(select(CustomerDesign).where(CustomerDesign.id == did))
        except Exception:  # noqa: BLE001 — bozuk id kaydı onayı bozmasın
            continue
        # Rötuşlanmış numune varsa müşteri ONU görsün; yoksa stüdyo önizlemesi
        gosterilecek = d.proof_path or d.preview_path if d else None
        if not gosterilecek:
            continue
        from app.services.storage import design_render_url
        _li = kalem_of.get(str(did))
        out.append({
            "line_item_id": str(_li.id) if _li is not None else None,
            "slot": 1,
            # Sürüm damgalı: numune/baskı yeniden üretilince müşteriye ESKİ
            # kopya gösterilmesin (dosya adı sabit, adres değişmiyordu)
            "image_url": _absolute(design_render_url(gosterilecek) or ""),
            "file_url": (_absolute(design_render_url(d.print_path))
                         if d.print_path else None),
            "file_format": "png",
            "title": f"{d.name} (kendi tasarımı)"
                     + ("" if d.proof_path else " — numune hazırlanmadı"),
            "quantity": 1,
            "is_mockup": True,
        })
    return out


def approval_link(token: str) -> str:
    base = get_settings().support_public_base_url.rstrip("/")
    return f"{base}/onay/{token}"


def build_message(order: Order, link: str, *, revizyon: bool = False) -> str:
    """Müşteriye gönderilmeye hazır mesaj (operatör elle WhatsApp/Instagram'dan yollar).

    `revizyon=True` (2. ve sonraki versiyonlar): müşteri zaten bir tasarım
    görmüş ve revizyon istemiş. "hazırladık" demek onu yeni bir tasarım
    bekliyormuş gibi karşılar; "TEKRAR hazırladık" isteğinin karşılandığını
    söyler.
    """
    ad = (order.customer_name or "").split()[0] if order.customer_name else ""
    no = order.name or f"#{order.order_number}"
    merhaba = f"Merhaba {ad}," if ad else "Merhaba,"
    hazir = "tekrar hazırladık" if revizyon else "hazırladık"
    return (
        f"{merhaba}\n\n{no} numaralı siparişinizin tasarımını {hazir}. "
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
