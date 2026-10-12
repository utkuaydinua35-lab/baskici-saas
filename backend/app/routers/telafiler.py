"""Telafiler API — /api/telafiler.

Telafi siparisi: hatali model secimi / yanlis hazirlama yuzunden musteriye
tekrar gonderilecek urunler. Telafi = is_telafi=True isaretli bir Order kaydi.
Boylece kalip olusturucu + 9 asamali pipeline + line item/tasarim altyapisi
oldugu gibi yeniden kullanilir.

Olusturma 2 yolla:
  1) Mevcut siparisten klonla (line item subset) -> /from-order/{order_id}
  2) Sifirdan elle -> /manual

Eslestirme: telafi_kaynak_order_id ile normal siparise baglanir. Normal
siparis detayinda bu telafiler + guncel asamalari gosterilir.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, func as sql_func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import get_current_user, require_permission
from app.database import get_db
from app.services import tasarim_kapsam
from app.models import Design, LineItem, Order, OrderStatusHistory, Store, User
from app.stages import all_stages_payload, is_valid_stage, progress_percent, stage_info

router = APIRouter(prefix="/api/telafiler", tags=["telafiler"],
    dependencies=[Depends(require_permission("siparisler"))],
)


# ───────────────────────── Serializer ─────────────────────────

def _li_thumbnail(li: LineItem, db: Session | None = None) -> str | None:
    """Urun gorseli — order_detail._serialize_line_item ile ayni mantik:
    raw image -> Design/KisiyeOzel product_id -> atanmis tasarim thumbnail."""
    from app.services import storage
    from app.models import KisiyeOzelProduct

    raw = li.raw or {}
    for path in [("image",), ("image_url",), ("product", "image")]:
        v = raw
        ok = True
        for p in path:
            if isinstance(v, dict):
                v = v.get(p)
            else:
                ok = False
                break
        if ok and isinstance(v, str) and v.startswith("http"):
            return v

    if db is not None and li.product_id:
        pid = str(li.product_id)
        d = db.scalar(select(Design).where(
            Design.product_id == pid, Design.product_image_url.isnot(None)))
        if d and d.product_image_url:
            return d.product_image_url
        kop = db.scalar(select(KisiyeOzelProduct).where(
            KisiyeOzelProduct.product_id == pid,
            KisiyeOzelProduct.product_image_url.isnot(None)))
        if kop and kop.product_image_url:
            return kop.product_image_url

    if getattr(li, "product_image_url", None):
        return li.product_image_url
    d = li.assigned_design
    if d and getattr(d, "file_path", None):
        try:
            t = storage.get_thumbnail_url(d.file_path, d.file_format)
            if t:
                return t
        except Exception:
            pass
    return None


def _ser_li(li: LineItem, db: Session | None = None) -> dict:
    return {
        "id": str(li.id),
        "title": li.title,
        "variant_title": li.variant_title,
        "quantity": li.quantity,
        "device_model": li.device_model_override
        or next(
            (p.get("value") for p in (li.properties or [])
             if isinstance(p, dict) and (p.get("name") or "").endswith("Model")),
            None,
        ),
        "design_code": (li.assigned_design.code if li.assigned_design else None),
        "design_name": (li.assigned_design.name if li.assigned_design else None),
        "thumbnail_url": _li_thumbnail(li, db),
        "is_kaliba_eklendi": bool(li.is_kaliba_eklendi),
    }


def _ser_telafi(o: Order, detay: bool = False, db: Session | None = None) -> dict:
    si = stage_info(o.current_stage)
    kaynak = o.telafi_kaynak
    d = {
        "id": str(o.id),
        "store_id": str(o.store_id),
        "order_number": o.order_number,
        "customer_name": o.customer_name,
        "telafi_sebep": o.telafi_sebep,
        "current_stage": o.current_stage,
        "current_stage_info": si,
        "progress_percent": progress_percent(o.current_stage),
        "fulfillment_status": o.fulfillment_status,
        "is_iptal": o.is_iptal,
        "created_at_platform": o.created_at_platform.isoformat() if o.created_at_platform else None,
        "kaynak": (
            {
                "id": str(kaynak.id),
                "order_number": kaynak.order_number,
                "customer_name": kaynak.customer_name,
            }
            if kaynak else None
        ),
        "item_count": len(o.line_items or []),
        # Kargo durumu: sipariş detayındaki "barkod oluştur / yeniden yazdır"
        # düğmesi bunu okur (telafi de müşteriye kargoyla gidiyor).
        "kargo": {
            "takip_no": (o.kargo_info or {}).get("takip_no") or None,
            "handler_name": (o.kargo_info or {}).get("handler_name") or None,
            "var": bool((o.kargo_info or {}).get("takip_no")),
            "kargoda": (o.current_stage or 1) >= 8,
        },
    }
    if detay:
        d["line_items"] = [_ser_li(li, db) for li in (o.line_items or [])]
        d["note"] = o.note
    return d


# ───────────────────────── Liste / meta ─────────────────────────

@router.get("/_meta/stages", response_model=None)
def telafi_stages(user: User = Depends(get_current_user)):
    return {"stages": all_stages_payload()}


@router.get("", response_model=None)
def list_telafiler(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Tum telafi siparislerini listele (yeniden eskiye)."""
    rows = db.scalars(
        select(Order)
        .where(Order.tenant_id == user.tenant_id, Order.is_telafi == True)  # noqa: E712
        .options(
            selectinload(Order.line_items).selectinload(LineItem.assigned_design),
            selectinload(Order.telafi_kaynak),
        )
        .order_by(desc(Order.created_at_platform), desc(Order.fetched_at))
    ).all()
    return {"items": [_ser_telafi(o) for o in rows]}


@router.get("/_meta/stores", response_model=None)
def telafi_stores(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Magaza + bayii listesi. stores: gercek magazalar; dealers: bayiler
    (her birinin sanal store_id'si ile)."""
    from app.models import Dealer
    stores = db.scalars(select(Store).where(Store.tenant_id == user.tenant_id)).all()
    dealers = db.scalars(
        select(Dealer).where(Dealer.tenant_id == user.tenant_id, Dealer.is_active == True)  # noqa: E712
    ).all()
    return {
        "stores": [
            {"id": str(s.id), "name": s.name}
            for s in stores if getattr(s, "platform", None) != "bayii"
        ],
        "dealers": [
            {"id": str(de.id), "name": de.name, "store_id": str(de.store_id)}
            for de in dealers if de.store_id
        ],
    }


@router.get("/searchable-orders", response_model=None)
def searchable_orders(
    q: str = Query("", min_length=0),
    store_id: uuid.UUID | None = Query(None),
    durum: str = Query("all"),  # all | acik | gonderilmis
    limit: int = Query(30, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Klonlama/eslestirme icin normal (telafi olmayan) siparis ara.
    Filtreler: q (no/musteri), store_id, durum (acik/gonderilmis)."""
    query = (
        select(Order)
        .where(Order.tenant_id == user.tenant_id, Order.is_telafi == False)  # noqa: E712
        .options(
            selectinload(Order.line_items).selectinload(LineItem.assigned_design),
            selectinload(Order.store),
        )
    )
    if store_id:
        query = query.where(Order.store_id == store_id)
    if durum == "gonderilmis":
        query = query.where(Order.fulfillment_status == "fulfilled")
    elif durum == "acik":
        # "Açık" kelimesi panelde HER YERDE aynı şeyi demeli (services/order_scope).
        from app.services.order_scope import acik_kosullar
        query = query.where(*acik_kosullar())
    s = (q or "").strip()
    if s:
        like = f"%{s}%"
        query = query.where(
            or_(Order.order_number.ilike(like), Order.customer_name.ilike(like))
        )
    query = query.order_by(desc(Order.created_at_platform)).limit(limit)
    rows = db.scalars(query).all()
    return {
        "items": [
            {
                "id": str(o.id),
                "order_number": o.order_number,
                "customer_name": o.customer_name,
                "store_id": str(o.store_id),
                "store_name": (o.store.name if o.store else None),
                "fulfillment_status": o.fulfillment_status,
                "created_at_platform": o.created_at_platform.isoformat() if o.created_at_platform else None,
                "item_count": len(o.line_items or []),
                # Arama listesinde thumbnail kullanilmiyor (klonlamada gorseller /detail'den
                # gelir) -> db=None ile satir basina Design/KisiyeOzel sorgularini atla (N+1 onler)
                "line_items": [_ser_li(li) for li in (o.line_items or [])],
            }
            for o in rows
        ]
    }


@router.get("/_trash", response_model=None)
def list_telafi_trash(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Silinmis telafiler (cop kutusu)."""
    rows = db.scalars(
        select(Order)
        .where(
            Order.tenant_id == user.tenant_id,
            Order.is_telafi == True,  # noqa: E712
            Order.deleted_at.isnot(None),
        )
        .options(selectinload(Order.line_items), selectinload(Order.telafi_kaynak))
        .order_by(desc(Order.deleted_at))
        .execution_options(include_deleted=True)
    ).all()
    return {"items": [
        {
            "id": str(o.id), "order_number": o.order_number,
            "customer_name": o.customer_name, "telafi_sebep": o.telafi_sebep,
            "item_count": len(o.line_items or []),
            "deleted_at": o.deleted_at.isoformat() if o.deleted_at else None,
        }
        for o in rows
    ]}


@router.get("/{telafi_id}", response_model=None)
def get_telafi(
    telafi_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    o = db.scalar(
        select(Order)
        .where(Order.id == telafi_id, Order.tenant_id == user.tenant_id, Order.is_telafi == True)  # noqa: E712
        .options(
            selectinload(Order.line_items).selectinload(LineItem.assigned_design),
            selectinload(Order.telafi_kaynak),
        )
    )
    if not o:
        raise HTTPException(status_code=404, detail="Telafi bulunamadi")
    return _ser_telafi(o, detay=True, db=db)


# ───────────────────────── Olusturma ─────────────────────────

def _yeni_telafi_kodu(db: Session, tenant_id) -> str:
    """T-1, T-2 ... benzersiz telafi siparis kodu uret.

    ⚠ Eskiden telafi SAYISI + 1'di. Sayım global soft-delete süzgecinden
    geçtiği için çöpe atılan telafi sayıdan düşüyor ve AYNI kod yeniden
    veriliyordu (canlıda T-1 iki, T-8 üç kez). İki kişi aynı anda telafi
    açınca da çakışıyordu. Artık silinenler dahil EN BÜYÜK kod + 1, işlem
    boyunca kiracı başına kilitli.
    """
    import re
    from sqlalchemy import text as _text
    db.execute(_text("select pg_advisory_xact_lock(hashtext(:k))"),
               {"k": f"telafi-kodu:{tenant_id}"})
    numaralar = db.scalars(
        select(Order.order_number)
        .where(Order.tenant_id == tenant_id, Order.is_telafi == True)  # noqa: E712
        .execution_options(include_deleted=True)
    ).all()
    en_buyuk = max((int(m.group(1)) for n in numaralar
                    if (m := re.search(r"T-(\d+)$", n or ""))), default=0)
    return f"T-{en_buyuk + 1}"


class CloneIn(BaseModel):
    line_item_ids: list[uuid.UUID]
    telafi_sebep: str | None = None
    # Kalem başına telafi adedi (verilmezse kalemin kendi adedi). Örn. 2 adetlik
    # kalemden yalnız 1'i hatalıysa 1 yazılır; kaynaktakinden fazla olamaz.
    adetler: dict[uuid.UUID, int] | None = None


@router.post("/from-order/{order_id}", response_model=None)
def create_from_order(
    order_id: uuid.UUID,
    body: CloneIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mevcut siparisten SECILI line item'lari klonlayarak telafi siparisi olustur.
    Tum urunler telafi olmak zorunda degil (orn 4 urunden 1'i)."""
    src = db.scalar(
        select(Order)
        .where(Order.id == order_id, Order.tenant_id == user.tenant_id)
        .options(selectinload(Order.line_items))
    )
    if not src:
        raise HTTPException(status_code=404, detail="Kaynak siparis bulunamadi")
    if not body.line_item_ids:
        raise HTTPException(status_code=400, detail="En az bir urun secmelisin")

    sec = {str(x) for x in body.line_item_ids}
    src_lis = [li for li in (src.line_items or []) if str(li.id) in sec]
    if not src_lis:
        raise HTTPException(status_code=400, detail="Secilen urunler kaynak sipariste bulunamadi")
    adetler = {str(k): v for k, v in (body.adetler or {}).items()}
    for li in src_lis:
        a = adetler.get(str(li.id))
        if a is not None and not 1 <= a <= max(1, int(li.quantity or 1)):
            raise HTTPException(status_code=400,
                                detail=f"{(li.title or '')[:40]}: telafi adedi 1 ile {li.quantity or 1} arasında olmalı")

    kod = _yeni_telafi_kodu(db, user.tenant_id)
    telafi = Order(
        tenant_id=user.tenant_id,
        store_id=src.store_id,
        external_id=f"telafi_{kod}_{uuid.uuid4().hex[:6]}",
        order_number=f"{src.order_number}{kod}",
        name=f"#{src.order_number} TELAFI",
        fulfillment_status=None,
        financial_status=None,
        customer_name=src.customer_name,
        customer_email=src.customer_email,
        created_at_platform=datetime.now(timezone.utc),
        note=src.note,
        tags="telafi",
        is_telafi=True,
        telafi_kaynak_order_id=src.id,
        telafi_sebep=(body.telafi_sebep or "").strip() or None,
        raw={"telafi": True, "kaynak_order_number": src.order_number,
             "customer_phone": (src.raw or {}).get("customer_phone"),
             "shipping_address": (src.raw or {}).get("shipping_address")},
    )
    db.add(telafi)
    db.flush()

    for pos, li in enumerate(sorted(src_lis, key=lambda x: x.position or 0)):
        db.add(LineItem(
            tenant_id=user.tenant_id,
            order_id=telafi.id,
            external_id=None,
            product_id=li.product_id,
            variant_id=li.variant_id,
            title=li.title,
            variant_title=li.variant_title,
            sku=li.sku,
            quantity=adetler.get(str(li.id)) or li.quantity,
            position=pos,
            properties=list(li.properties or []),
            raw={"telafi": True, "kaynak_line_item_id": str(li.id)},
            assigned_design_id=li.assigned_design_id,
            device_model_override=li.device_model_override,
            # ⚠ Çift kılıfın 2. yarısı ve elle seçilmiş varyasyon da kopyalanmalı:
            # eksik kalınca telafi kalıba yanlış renkte / tek kılıf olarak giriyordu.
            assigned_design_id_2=li.assigned_design_id_2,
            device_model_override_2=li.device_model_override_2,
            kilif_varyasyon=li.kilif_varyasyon,
            kilif_varyasyon_2=li.kilif_varyasyon_2,
            birincil_renk=li.birincil_renk,
            ikincil_renk=li.ikincil_renk,
            ucuncu_renk=li.ucuncu_renk,
            product_image_url=li.product_image_url,
        ))

    # Kaynak siparişin geçmişine iz: telafi ne zaman, neden açıldı görülsün.
    db.add(OrderStatusHistory(
        tenant_id=user.tenant_id, order_id=src.id,
        from_stage=src.current_stage, to_stage=src.current_stage,
        action="telafi_olusturuldu",
        note=f"Telafi {telafi.order_number} · {len(src_lis)} ürün"
             + (f" · {telafi.telafi_sebep}" if telafi.telafi_sebep else ""),
        created_by=user.full_name or user.email,
    ))
    db.commit()
    db.refresh(telafi)
    return _ser_telafi(telafi, detay=True, db=db)


class ManualLI(BaseModel):
    title: str
    quantity: int = 1
    device_model: str | None = None
    design_id: uuid.UUID | None = None
    color: str | None = None
    notes: str | None = None


class ManualTelafiIn(BaseModel):
    store_id: uuid.UUID
    dealer_id: uuid.UUID | None = None
    customer_name: str
    customer_email: str | None = None
    customer_phone: str | None = None
    telafi_sebep: str | None = None
    note: str | None = None
    line_items: list[ManualLI]


@router.post("/manual", response_model=None)
def create_manual_telafi(
    body: ManualTelafiIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sifirdan elle telafi siparisi olustur."""
    store = db.scalar(select(Store).where(Store.id == body.store_id, Store.tenant_id == user.tenant_id))
    if not store:
        raise HTTPException(status_code=404, detail="Magaza bulunamadi")
    if not body.customer_name.strip():
        raise HTTPException(status_code=400, detail="Musteri adi zorunlu")
    if not body.line_items:
        raise HTTPException(status_code=400, detail="En az bir urun eklemelisin")

    kod = _yeni_telafi_kodu(db, user.tenant_id)
    telafi = Order(
        tenant_id=user.tenant_id,
        store_id=body.store_id,
        external_id=f"telafi_{kod}_{uuid.uuid4().hex[:6]}",
        order_number=kod,
        name=f"#{kod} TELAFI",
        fulfillment_status=None,
        financial_status=None,
        customer_name=body.customer_name.strip(),
        customer_email=body.customer_email,
        created_at_platform=datetime.now(timezone.utc),
        note=body.note,
        tags="telafi",
        is_telafi=True,
        telafi_sebep=(body.telafi_sebep or "").strip() or None,
        raw={"telafi": True, "manual": True, "customer_phone": body.customer_phone,
             **({"dealer_id": str(body.dealer_id)} if body.dealer_id else {})},
    )
    db.add(telafi)
    db.flush()

    for pos, li in enumerate(body.line_items):
        if not (li.title or "").strip():
            raise HTTPException(status_code=400, detail=f"Urun #{pos+1}: baslik zorunlu")
        design = None
        if li.design_id:
            design = db.scalar(select(Design).where(
                Design.id == li.design_id, tasarim_kapsam.kosul(db, body.store_id),
                Design.tenant_id == user.tenant_id))
            if not design:
                raise HTTPException(status_code=400, detail=f"Urun #{pos+1}: tasarim bulunamadi")
        if li.device_model:
            from app.services._private import case_dimensions as _cd
            if not _cd.has_spec(li.device_model):
                raise HTTPException(status_code=400, detail=f"Urun #{pos+1}: model taninmadi '{li.device_model}'")
        properties = []
        if li.device_model:
            properties.append({"name": "Telefon Modeli", "value": li.device_model})
        if li.notes:
            properties.append({"name": "Not", "value": li.notes})
        db.add(LineItem(
            tenant_id=user.tenant_id,
            order_id=telafi.id,
            title=li.title.strip(),
            quantity=max(1, int(li.quantity or 1)),
            position=pos,
            properties=properties,
            raw={"telafi": True, "manual": True, "notes": li.notes},
            assigned_design_id=design.id if design else None,
            # Okunur ad — ölçü aynı kalmak şartıyla (phone_models.gorunen_ad)
            device_model_override=_pm_gorunen_ad(db, user.tenant_id, li.device_model),
            birincil_renk=li.color,
        ))

    db.commit()
    db.refresh(telafi)
    return _ser_telafi(telafi, detay=True, db=db)


# ───────────────────────── Eslestirme / asama / sil ─────────────────────────

class MatchIn(BaseModel):
    order_id: uuid.UUID | None = None


def _get_telafi(db, telafi_id, tenant_id) -> Order:
    o = db.scalar(select(Order).where(
        Order.id == telafi_id, Order.tenant_id == tenant_id, Order.is_telafi == True))  # noqa: E712
    if not o:
        raise HTTPException(status_code=404, detail="Telafi bulunamadi")
    return o


class TelafiKargoIn(BaseModel):
    il: str = ""      # adres çözülemezse elle il
    ilce: str = ""    # adres çözülemezse elle ilçe


@router.post("/{telafi_id}/kargo-barkod", response_model=None)
def telafi_kargo_barkod(telafi_id: uuid.UUID, body: TelafiKargoIn = TelafiKargoIn(),
                        user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Telafi için kargo gönderisi + barkod oluştur — sipariş detayından.

    ⚠ Paketleme ekranındaki akışın AYNISI çağrılır (kopya DEĞİL): gönderi
    oluşur, kargo bilgisi saklanır, aşama 8'e geçer, stok düşer, vitrin
    siparişinde müşteriye kargo e-postası gider. Telafi paketleme kuyruğuna
    girmeden elden kargoya verildiğinde bu düğme gerekiyordu.
    """
    from app.routers.packaging import KargoGonderRequest, kargo_gonder

    t = _get_telafi(db, telafi_id, user.tenant_id)
    if (t.kargo_info or {}).get("takip_no"):
        raise HTTPException(409, "Bu telafinin kargo barkodu zaten var — "
                                 "yeniden yazdırabilir ya da iptal edebilirsin")
    return kargo_gonder(str(t.id), KargoGonderRequest(il=body.il, ilce=body.ilce),
                        user=user, db=db)


@router.post("/{telafi_id}/kargo-iptal", response_model=None)
def telafi_kargo_iptal(telafi_id: uuid.UUID, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    """Yanlış oluşturulan telafi kargosunu iptal et (barkod silinir, aşama geri alınır).

    Barkod yanlış telafide oluşturulabiliyor; oluşturmanın karşılığı olan geri
    alma da aynı ekranda olmalı. Paketlemedeki iptal akışının AYNISI çağrılır.
    """
    from app.routers.packaging import kargo_iptal

    t = _get_telafi(db, telafi_id, user.tenant_id)
    return kargo_iptal(str(t.id), user=user, db=db)


# Etiket uçları paketlemede de var ama oraya "paketleme" yetkisi gerekiyor;
# sipariş detayını kullanan (yalnız "siparisler" yetkili) personel barkodu
# yazdıramıyordu. Aynı işlevler telafi kapsamında da açılıyor — iş yine
# paketlemedeki fonksiyonlarda yapılıyor, kopya kod yok.
@router.get("/{telafi_id}/kargo-label", response_model=None)
def telafi_kargo_label(telafi_id: uuid.UUID, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    """Telafinin kargo etiketini yeniden getir (Basit Kargo SVG / Sürat PDF)."""
    from app.routers.packaging import kargo_label

    t = _get_telafi(db, telafi_id, user.tenant_id)
    return kargo_label(str(t.id), user=user, db=db)


@router.get("/{telafi_id}/zpl", response_model=None)
def telafi_zpl(telafi_id: uuid.UUID, tip: str = "kargo", dpi: int = 203,
               w_mm: float = 0, h_mm: float = 0, doldur: bool = True,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Telafi etiketini ZPL olarak ver — Zebra/QZ'ye doğrudan basmak için."""
    from app.routers.packaging import order_zpl

    t = _get_telafi(db, telafi_id, user.tenant_id)
    return order_zpl(str(t.id), tip=tip, dpi=dpi, w_mm=w_mm, h_mm=h_mm,
                     doldur=doldur, user=user, db=db)


@router.patch("/{telafi_id}/match", response_model=None)
def match_telafi(
    telafi_id: uuid.UUID,
    body: MatchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Telafiyi normal bir siparisle eslestir (veya order_id=None ile esi kaldir)."""
    o = _get_telafi(db, telafi_id, user.tenant_id)
    if body.order_id is None:
        o.telafi_kaynak_order_id = None
    else:
        kaynak = db.scalar(select(Order).where(
            Order.id == body.order_id, Order.tenant_id == user.tenant_id, Order.is_telafi == False))  # noqa: E712
        if not kaynak:
            raise HTTPException(status_code=404, detail="Eslestirilecek siparis bulunamadi")
        o.telafi_kaynak_order_id = kaynak.id
    db.commit()
    db.refresh(o)
    return _ser_telafi(o, detay=True, db=db)


class StageIn(BaseModel):
    current_stage: int
    note: str | None = None


@router.patch("/{telafi_id}/stage", response_model=None)
def update_stage(
    telafi_id: uuid.UUID,
    body: StageIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    o = _get_telafi(db, telafi_id, user.tenant_id)
    if not is_valid_stage(body.current_stage):
        raise HTTPException(status_code=400, detail="Gecersiz asama")
    eski = o.current_stage
    o.current_stage = body.current_stage
    db.add(OrderStatusHistory(
        tenant_id=user.tenant_id, order_id=o.id,
        from_stage=eski, to_stage=body.current_stage,
        action="stage_change", note=body.note,
        created_by=getattr(user, "email", None),
    ))
    db.commit()
    return {"ok": True, "current_stage": o.current_stage}


@router.delete("/{telafi_id}", status_code=204)
def delete_telafi(
    telafi_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soft-delete: cop kutusundan geri alinabilir."""
    o = _get_telafi(db, telafi_id, user.tenant_id)
    o.deleted_at = datetime.now(timezone.utc)
    db.commit()


@router.post("/{telafi_id}/restore", response_model=None)
def restore_telafi(
    telafi_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Silinmis telafiyi geri al."""
    o = db.scalar(
        select(Order)
        .where(Order.id == telafi_id, Order.tenant_id == user.tenant_id, Order.is_telafi == True)  # noqa: E712
        .execution_options(include_deleted=True)
    )
    if not o:
        raise HTTPException(status_code=404, detail="Telafi bulunamadi")
    o.deleted_at = None
    db.commit()
    return {"ok": True}


def _pm_gorunen_ad(db, tenant_id, model):
    """Siparişe yazılan model adı okunur olsun — ölçü aynı kalmak şartıyla."""
    from app.services.phone_models import gorunen_ad
    return gorunen_ad(db, tenant_id, model)
