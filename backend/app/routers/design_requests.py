"""
Tasarım Talepleri (admin) — /api/design-requests/*

Müşterilerin hesaplarından yükledikleri tasarım talepleri; panel inceler,
durum + not günceller (müşteri hesabında görünür).
"""
from __future__ import annotations

import uuid

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.database import get_db
from app.models import DesignRequest, Store, User
from app.services import activity, ozel_urun

router = APIRouter(
    prefix="/api/design-requests", tags=["design-requests"],
    dependencies=[Depends(require_permission("vitrin"))],
)

STATUSES = {"acik", "incelendi", "teklif", "tamam", "red"}


class DesignRequestUpdate(BaseModel):
    status: str | None = None
    admin_note: str | None = Field(None, max_length=2000)
    notify_customer: bool = False  # true ise müşteriye durum/not e-postası gider


@router.get("", response_model=dict)
def list_requests(
    store_id: uuid.UUID = Query(...),
    status_f: str | None = Query(None, alias="status"),
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    q = select(DesignRequest).where(
        DesignRequest.tenant_id == user.tenant_id,
        DesignRequest.store_id == store_id,
    ).order_by(DesignRequest.created_at.desc()).limit(200)
    if status_f in STATUSES:
        q = q.where(DesignRequest.status == status_f)
    rows = db.scalars(q).all()
    store = db.get(Store, store_id)
    return {"requests": [_ser(db, store, r) for r in rows]}


def _ser(db: Session, store: Store | None, r: DesignRequest) -> dict:
    return {"id": str(r.id), "customer_email": r.customer_email,
            "customer_name": r.customer_name, "image_url": r.image_url,
            "message": r.message, "phone_model": r.phone_model,
            "status": r.status, "admin_note": r.admin_note,
            "customer_phone": ozel_urun.musteri_telefonu(db, store, r) if store else None,
            "urun": ozel_urun.urun_ozeti(db, store, r) if store else None,
            "bildirildi_at": r.bildirildi_at.isoformat() if r.bildirildi_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None}


def _talep(db: Session, user: User, request_id) -> tuple[DesignRequest, Store]:
    r = db.scalar(select(DesignRequest).where(
        DesignRequest.id == request_id, DesignRequest.tenant_id == user.tenant_id))
    if not r:
        raise HTTPException(404, "Talep bulunamadı")
    return r, db.get(Store, r.store_id)


@router.get("/secenekler", response_model=dict)
def ozel_urun_secenekleri(
    store_id: uuid.UUID = Query(...),
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Özel ürün formu için: model setleri ve kılıf şablonları (ürün fotoğrafı)."""
    from app.models import CaseTemplate, VariantSet
    setler = db.scalars(select(VariantSet).where(
        VariantSet.tenant_id == user.tenant_id, VariantSet.store_id == store_id)
        .order_by(VariantSet.name)).all()
    vars_ = ozel_urun.varsayilan_set(db, store_id)
    kiliflar = db.scalars(select(CaseTemplate).where(
        CaseTemplate.tenant_id == user.tenant_id, CaseTemplate.store_id == store_id,
        CaseTemplate.image_path.isnot(None)).order_by(CaseTemplate.position)).all()
    return {"setler": [{"id": str(v.id), "name": v.name, "adet": len(v.items or [])} for v in setler],
            "varsayilan_set": str(vars_.id) if vars_ else None,
            "kiliflar": [{"id": str(t.id), "label": t.label} for t in kiliflar]}


@router.post("/{request_id}/urun", response_model=dict)
def ozel_urun_kaydet(
    request_id: uuid.UUID,
    fiyat: float = Form(..., gt=0, le=100000),
    baslik: str | None = Form(None, max_length=300),
    variant_set_id: uuid.UUID | None = Form(None),
    template_id: uuid.UUID | None = Form(None),
    baski: UploadFile | None = File(None),
    # Ürünün görselleri — sırasıyla, ilki kapak (en çok 8)
    gorsel: list[UploadFile] | None = File(None),
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Talebe özel ürünü kur/güncelle. Yüklenen görseller ürünün görselleri olur;
    görsel gönderilmezse mevcutlar aynen kalır. Ürün YALNIZ linkle açılır."""
    r, store = _talep(db, user, request_id)
    def oku(f: UploadFile | None):
        if f is None or not f.filename:
            return None
        veri = f.file.read()
        return (veri, f.filename) if veri else None
    try:
        urun = ozel_urun.urun_kur(db, store, r, fiyat=fiyat, baslik=baslik,
                                  baski=oku(baski),
                                  gorseller=[x for x in (oku(g) for g in (gorsel or [])) if x],
                                  variant_set_id=variant_set_id, template_id=template_id)
    except ValueError as e:
        db.rollback()
        raise HTTPException(422, str(e))
    activity.record(db, user, "ozel_urun_kaydet", store_id=store.id, entity_type="urun",
                    entity_id=urun.id, entity_label=urun.title)
    db.commit()
    db.refresh(r)
    return _ser(db, store, r)


@router.delete("/{request_id}/urun", response_model=dict)
def ozel_urun_kaldir(
    request_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Ürünü satıştan kaldır (arşivle, link açılmaz). Silinmez: verilmiş
    siparişler ürünü göstermeye devam eder; tekrar kaydedince açılır."""
    from app.models import CatalogProduct
    r, store = _talep(db, user, request_id)
    u = db.get(CatalogProduct, r.product_id) if r.product_id else None
    if u:
        u.status = "archived"
        db.commit()
    return _ser(db, store, r)


@router.patch("/{request_id}", response_model=dict)
def update_request(
    request_id: uuid.UUID,
    body: DesignRequestUpdate,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    r = db.scalar(select(DesignRequest).where(
        DesignRequest.id == request_id, DesignRequest.tenant_id == user.tenant_id))
    if not r:
        raise HTTPException(404, "Talep bulunamadı")
    if body.status is not None:
        if body.status not in STATUSES:
            raise HTTPException(422, "Geçersiz durum")
        r.status = body.status
    if body.admin_note is not None:
        r.admin_note = body.admin_note.strip() or None
    db.commit()

    # Bildirim istendiyse her zaman gönder — değişiklik olmasa da mevcut
    # durum+notu yeniden iletmek meşru (admin açıkça istedi).
    notified = False
    whatsapp = None
    if body.notify_customer:
        store = db.get(Store, r.store_id)
        ozet = ozel_urun.urun_ozeti(db, store, r) if store else None
        if r.customer_email:
            notified = _notify_customer(db, r, ozet)
        # WhatsApp: mesaj hazır bağlantı olarak döner, panel yeni sekmede açar
        # (gönder tuşuna mağaza basar — işletme hesabından otomatik gönderim yok)
        tel = ozel_urun.musteri_telefonu(db, store, r) if store else None
        if tel and store:
            from app.services.meta_capi import tr_telefon
            from urllib.parse import quote
            no = tr_telefon(tel)
            if no:
                whatsapp = f"https://wa.me/{no}?text={quote(ozel_urun.whatsapp_metni(store, r, ozet))}"
        r.bildirildi_at = datetime.now(timezone.utc)
        db.commit()
    return {"ok": True, "status": r.status, "notified": notified, "whatsapp_url": whatsapp}


STATUS_TR = {"acik": "İnceleme bekliyor", "incelendi": "İncelendi",
             "teklif": "Teklif hazırlandı", "tamam": "Tamamlandı", "red": "Uygun değil"}


def _notify_customer(db: Session, r: DesignRequest, ozet: dict | None = None) -> bool:
    """Müşteriye durum/not e-postası — best-effort (SMTP yoksa sessizce False)."""
    try:
        from xml.sax.saxutils import escape

        from app.models import Store
        from app.services import email_service
        # 2026-09-08: site_url import EDILMEMISTI -> NameError, asagidaki
        # except onu yutuyordu ve fonksiyon her zaman False donuyordu; yani
        # tasarim talebi durum e-postasi hic gonderilmedi.
        from app.services.site import site_url

        store = db.get(Store, r.store_id)
        if not store:
            return False
        cfg = store.config or {}
        site = site_url(cfg)
        tenant = getattr(store, "tenant", None)
        brand = email_service.brand_kwargs(tenant) if tenant else {}
        label = STATUS_TR.get(r.status, r.status)
        note_html = ""
        if r.admin_note:
            note_html = email_service.highlight_box(
                f"💬 {escape(r.admin_note)}")
        if ozet and ozet.get("satista"):
            # Özel ürün hazır: link + fiyat, düğme doğrudan ürüne
            gorsel = ""
            if ozet.get("image_url") and site:
                gorsel = (f"<p style='text-align:center'><img src='{escape(site + ozet['image_url'])}' "
                          "alt='' width='260' style='max-width:100%;border-radius:12px'></p>")
            html = email_service.render_email(
                title="Size özel ürününüz hazır 🎉",
                body_html=(
                    f"<p>Merhaba{' ' + escape(r.customer_name) if r.customer_name else ''},</p>"
                    "<p>Tasarım talebiniz için ürününüzü hazırladık.</p>"
                    f"{gorsel}"
                    f"<p><b>{escape(ozet['title'])}</b><br>Fiyat: <b>{escape(ozel_urun.fiyat_metni(ozet['price']))}</b></p>"
                    "<p>Telefon modelinizi seçip sepete ekleyerek siparişinizi verebilirsiniz. "
                    "Kargo ve kampanyalar sepetinize göre uygulanır. Bu bağlantıyı istediğiniz "
                    "kadar kullanabilirsiniz.</p>"
                    f"{note_html}"
                ),
                button_text="Ürünüme Git",
                button_url=ozet["url"],
                preheader=f"{ozet['title']} — {ozel_urun.fiyat_metni(ozet['price'])}",
                emoji="🎨",
                **brand,
            )
            return email_service.send_email(
                r.customer_email, "Size özel ürününüz hazır", html)
        html = email_service.render_email(
            title="Tasarım talebiniz güncellendi",
            body_html=(
                f"<p>Merhaba{' ' + escape(r.customer_name) if r.customer_name else ''},</p>"
                f"<p>Yüklediğiniz tasarım için talebinizin durumu: <b>{escape(label)}</b></p>"
                f"{note_html}"
            ),
            button_text="Talebimi Görüntüle" if site else "",
            button_url=f"{site}/hesap" if site else "",
            preheader=f"Talep durumu: {label}",
            emoji="🎨",
            **brand,
        )
        return email_service.send_email(
            r.customer_email, f"Tasarım talebiniz: {label}", html)
    except Exception:  # noqa: BLE001 — bildirim talebi düşürmez
        return False
