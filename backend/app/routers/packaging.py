"""
Paketleme — /api/packaging/*

- GET  /api/packaging/order/{order_ref}            → sipariş + aksesuar eşleşme önerileri
- POST /api/packaging/order/{order_ref}/complete   → düşümleri uygula + stage 7
- GET  /api/packaging/order/{order_ref}/label      → kargo etiketi PDF
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import get_current_user, require_permission
from app.adapters import get_adapter
from app.database import get_db
from app.models import (
    AccessoryProduct, CoupleProduct, Dealer, Design, LineItem, Mold, MoldItem, Order,
    OrderStatusHistory, Store, User,
)
from app.services import basit_kargo, label_pdf, packaging as pkg, storage, surat
from app import stages as stage_defs

router = APIRouter(prefix="/api/packaging", tags=["packaging"],
    dependencies=[Depends(require_permission("paketleme"))],
)


def _resolve_order(db: Session, ref: str, tenant_id) -> Order:
    q = select(Order).where(Order.tenant_id == tenant_id).options(
        selectinload(Order.line_items)
    )
    order = None
    try:
        oid = uuid.UUID(str(ref))
        order = db.scalar(q.where(Order.id == oid))
    except (ValueError, AttributeError):
        order = None
    if not order:
        order = db.scalar(
            q.where((Order.order_number == ref) | (Order.name == ref))
            .order_by(desc(Order.created_at))
        )
    if not order:
        raise HTTPException(404, "Sipariş bulunamadı")
    return order


def _store_name(db: Session, order: Order) -> str | None:
    if not order.store_id:
        return None
    s = db.scalar(select(Store).where(Store.id == order.store_id))
    return s.name if s else None


class Deduction(BaseModel):
    stock_item_id: uuid.UUID
    quantity: int = 1


class CompleteRequest(BaseModel):
    deductions: list[Deduction] = []
    note: str | None = None


@router.get("/order/{order_ref}", response_model=dict)
def get_order(
    order_ref: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _resolve_order(db, order_ref, user.tenant_id)
    return {
        "order": {
            "id": str(order.id),
            "order_number": order.order_number,
            "name": order.name,
            "customer_name": order.customer_name,
            "current_stage": order.current_stage,
            "barkod_kodu": order.barkod_kodu,
            "store_name": _store_name(db, order),
        },
        "is_packaged": pkg.is_packaged(db, user.tenant_id, order),
        "suggestions": pkg.suggest_for_order(db, user.tenant_id, order),
    }


@router.post("/order/{order_ref}/complete", response_model=dict)
def complete(
    order_ref: str,
    body: CompleteRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _resolve_order(db, order_ref, user.tenant_id)
    deductions = [{"stock_item_id": d.stock_item_id, "quantity": d.quantity} for d in body.deductions]
    result = pkg.complete_packaging(db, user.tenant_id, order, deductions, user)

    if result["stage_changed"]:
        db.add(OrderStatusHistory(
            tenant_id=order.tenant_id,
            order_id=order.id,
            from_stage=None,
            to_stage=7,
            action="paketlendi",
            note=body.note or f"Paketlendi · {result['deducted']} stok düşüldü",
            created_by=user.full_name or user.email,
        ))

    db.commit()
    return result


@router.get("/il-ilce", response_model=dict)
def il_ilce(user: User = Depends(get_current_user)):
    """TR il → ilçe listesi (manuel il/ilçe seçimi için)."""
    from app.services import tr_iller
    return tr_iller.IL_ILCE


# Sürat ile DOĞRUDAN çalışma (Basit Kargo aracı olmadan). Sürat'ın kendi
# OrtakBarkodOlustur servisine gider; dönen takip no ve barkod Sürat'ın KENDİsidir,
# yani şubede geçerlidir. (57b9879'da başarısız olan şey panelin KENDİ ürettiği
# barkoddu — bu o değil.)
SURAT_DOGRUDAN = "DIRECT_SURAT"


def _surat_etiket_yolu(order_id) -> "Path":
    from pathlib import Path
    d = storage.STORAGE_ROOT / "cache" / "kargo_etiket"
    d.mkdir(parents=True, exist_ok=True)
    return Path(d) / f"{order_id}.pdf"


def _surat_gonderi(order, il_override: str | None, ilce_override: str | None) -> dict:
    """surat.create_shipment'i basit_kargo.create_shipment'in SÖZLEŞMESİNE çevir.

    Böylece kargo_gonder tek bir sonuç şekliyle çalışır. Sürat SVG değil base64
    PDF döndürdüğü için etiket diske yazılır; yeniden yazdırma oradan okur.
    """
    if not surat.is_configured():
        return {"ok": False, "message": "Sürat kullanıcı adı/şifre tanımlı değil (.env)"}
    r = surat.create_shipment(
        order.raw or {},
        ozel_kargo_takip_no=order.order_number or str(order.id),
        il_override=il_override, ilce_override=ilce_override,
    )
    if not r.get("ok"):
        return {"ok": False, "message": r.get("message") or "Sürat gönderisi oluşturulamadı",
                "ilce_eksik": r.get("ilce_eksik"), "il": r.get("il")}
    b64 = r.get("barkod_base64")
    if b64:
        import base64 as _b64
        try:
            _surat_etiket_yolu(order.id).write_bytes(_b64.b64decode(b64))
        except Exception:  # noqa: BLE001
            pass   # etiket yazılamazsa gönderi yine geçerli; yeniden yazdırma uyarır
    return {
        "ok": True,
        "takip_no": r.get("takip_no") or "",
        "handler_code": SURAT_DOGRUDAN,
        "handler_name": "Sürat Kargo",
        "provider": "surat",
        "etiket_var": bool(b64),
        "barkod_no": r.get("barkod_no"),
        "label_svg": None,      # Sürat PDF verir; yazdırma ZPL/PDF yolundan
        "id": None, "barcode": None, "status": r.get("message"),
    }


def _surat_etiket_pdf(db: Session, order, ki: dict) -> bytes:
    """Sürat gönderisinin YAZDIRILACAK etiketi.

    Sürat bu hesapta barkod GÖRSELİ döndürmüyor (takip no veriyor, Message=013,
    Barcode boş). Görsel varsa o kullanılır; yoksa kendi etiketimiz basılır ama
    üstünde SÜRAT'IN GERÇEK takip numarası Code128 olarak yer alır — o numara
    Sürat'ın sisteminde kayıtlı olduğu için şubede karşılığı vardır.
    """
    yol = _surat_etiket_yolu(order.id)
    if yol.exists():
        return yol.read_bytes()
    kod = (ki.get("barkod_no") or ki.get("takip_no") or "").strip()
    if not kod:
        raise HTTPException(404, "Sürat takip numarası yok — gönderiyi yeniden oluştur")
    from app.services import label_pdf as _lp
    return _lp.render_label_pdf(order, _store_name(db, order), barkod_kodu=kod,
                                kargo_firma=ki.get("handler_name") or "Sürat Kargo")


class KargoGonderRequest(BaseModel):
    il: str = ""    # manuel il (adres çözülemezse)
    ilce: str = ""  # manuel ilçe


@router.post("/order/{order_ref}/kargo-gonder", response_model=dict)
def kargo_gonder(
    order_ref: str,
    body: KargoGonderRequest = KargoGonderRequest(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Basit Kargo ile gönderi + barkod oluştur -> Shopify fulfillment + takip no -> stage 8.
    Kargo firması mağaza ayarından (store.config.kargo_handler) gelir.
    Döner: {ok, takip_no, handler_name, label_svg, id, barcode, shopify_ok, shopify_err}
    """
    order = _resolve_order(db, order_ref, user.tenant_id)
    if not order.store_id:
        raise HTTPException(400, "Siparişin mağazası yok")
    store = db.scalar(select(Store).where(Store.id == order.store_id))
    if not store:
        raise HTTPException(404, "Mağaza bulunamadı")

    handler_code = (store.config or {}).get("kargo_handler") or basit_kargo.DEFAULT_HANDLER

    # 1) Gönderi + barkod. Mağaza DIRECT_SURAT seçtiyse Sürat'a DOĞRUDAN gidilir,
    #    aksi halde Basit Kargo agregatörü üzerinden.
    if handler_code == SURAT_DOGRUDAN:
        res = _surat_gonderi(order, body.il.strip() or None, body.ilce.strip() or None)
    else:
        res = basit_kargo.create_shipment(
            order.raw or {},
            handler_code=handler_code,
            order_code=order.order_number or str(order.id),
            il_override=(body.il.strip() or None),
            ilce_override=(body.ilce.strip() or None),
        )
    if not res.get("ok"):
        raise HTTPException(400, res.get("message", "Kargo gönderimi başarısız"))

    takip_no = res.get("takip_no") or ""
    handler_label = res.get("handler_name") or basit_kargo.handler_name(handler_code)

    # 2) Shopify'a fulfillment + takip no yaz (hata olsa da kargo gönderisi oluştu, devam)
    shopify_ok = False
    shopify_err = None
    fulfillment_id = None
    try:
        shopify_oid = order.external_id or str((order.raw or {}).get("id") or "")
        if shopify_oid and store.platform == "shopify" and takip_no:
            adapter = get_adapter(store)
            tr = adapter.add_tracking(shopify_oid, takip_no, handler_label)
            shopify_ok = bool(tr.get("ok"))
            shopify_err = tr.get("error")
            fulfillment_id = (tr.get("fulfillment") or {}).get("id")
    except Exception as e:
        shopify_err = str(e)[:200]

    # 3) Kargo referansını sakla (re-print / iptal / webhook eşleşmesi için).
    # fulfillment_id + shopify_oid: gerçek takip no sonradan (webhook) gelince güncellemek için.
    order.kargo_info = {
        "provider": res.get("provider") or "basit",
        "etiket_var": res.get("etiket_var"),
        "barkod_no": res.get("barkod_no"),
        "id": res.get("id"),
        "barcode": res.get("barcode"),
        "takip_no": takip_no,
        "handler_code": res.get("handler_code") or handler_code,
        "handler_name": handler_label,
        "status": res.get("status"),
        "shopify_oid": (order.external_id or str((order.raw or {}).get("id") or "")) or None,
        "fulfillment_id": fulfillment_id,
    }

    # 4) Stage 8 (Kargoda) + history + stok düşümü
    prev_stage = order.current_stage or 1
    order.current_stage = 8
    # Kargoya verilince ana kalem/alt kalem stoğundan düş (idempotent, bloklamaz)
    try:
        from app.services import stock as _stock_svc
        _stock_svc.deduct_for_shipment(db, order.tenant_id, order, user)
    except Exception:
        pass
    db.add(OrderStatusHistory(
        tenant_id=order.tenant_id,
        order_id=order.id,
        from_stage=prev_stage,
        to_stage=8,
        action="kargoya_verildi",
        note=f"{handler_label} · takip {takip_no}" + ("" if shopify_ok else f" · Shopify yazılamadı: {shopify_err}"),
        created_by=user.full_name or user.email,
    ))

    # Vitrin siparişiyse müşteriye otomatik kargo bildirimi (bir kez, bloklamaz)
    from app.services.shipping_email import maybe_send_tracking_email
    maybe_send_tracking_email(db, order)

    db.commit()

    return {
        "ok": True,
        "takip_no": takip_no,
        "handler_name": handler_label,
        "label_svg": res.get("label_svg"),
        "id": res.get("id"),
        "barcode": res.get("barcode"),
        "status": res.get("status"),
        "shopify_ok": shopify_ok,
        "shopify_err": shopify_err,
    }


@router.post("/order/{order_ref}/kargo-iptal", response_model=dict)
def kargo_iptal(
    order_ref: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Kargo gönderisini iptal et: Basit Kargo barkodu sil + Shopify fulfillment iptal +
    stage 8->7 geri al + kargo_info temizle. Shopify/Basit hatasi akisi bloklamaz."""
    order = _resolve_order(db, order_ref, user.tenant_id)
    ki = order.kargo_info or {}
    # Kendi kargo anlaşmasında Basit Kargo kaydı YOKTUR; gönderi yalnızca
    # OrderShipment olarak durur (takip no bekliyor). İptal onu da tanımalı —
    # yoksa "iptal edilecek kargo yok" deyip sipariş Kargoda'da takılı kalıyordu.
    from app.models import OrderShipment as _OS
    _gonderiler = db.scalars(
        select(_OS).where(_OS.order_id == order.id, _OS.tenant_id == user.tenant_id)
        .order_by(desc(_OS.created_at))
    ).all()
    if not ki and not _gonderiler:
        raise HTTPException(400, "Bu siparişte iptal edilecek kargo gönderisi yok")

    # Sürat DOĞRUDAN gönderisinin iptali bizde yok: Sürat'ın iptal servisini
    # kullanmıyoruz. Yerel geri alma yine yapılır ama gönderi Sürat'ta DURUR —
    # sessizce "iptal edildi" demek yanlış olur, uyarı yanıta konur.
    surat_uyari = None
    if (ki.get("provider") or "") == "surat":
        surat_uyari = ("Gönderi Sürat'ta iptal EDİLMEDİ — Sürat şubesinden/panelinden "
                       "iptal etmen gerekiyor. Panelde sipariş geri alındı.")
    basit_ok = basit_kargo.cancel(ki.get("barcode")) if ki.get("barcode") else False

    # Gönderi kayıtlarını geri al — kalemler tekrar "gönderilmeyi bekleyen"e döner
    _silinen = 0
    if _gonderiler:
        from app.services import shipments as _sh
        for _g in _gonderiler:
            try:
                _sh.delete_shipment(db, order, _g.id, user_label=user.email)
                _silinen += 1
            except Exception:  # noqa: BLE001
                pass

    shopify_ok = False
    shopify_err = None
    try:
        fid = ki.get("fulfillment_id")
        if fid and order.store_id:
            store = db.scalar(select(Store).where(Store.id == order.store_id))
            if store and store.platform == "shopify":
                rr = get_adapter(store).cancel_fulfillment(str(fid))
                shopify_ok = bool(rr.get("ok"))
                shopify_err = rr.get("error")
    except Exception as e:  # noqa: BLE001
        shopify_err = str(e)[:200]

    prev_stage = order.current_stage or 8
    if prev_stage == 8:
        order.current_stage = 7  # Kargoda -> Paketleme'ye geri
    order.kargo_info = None
    db.add(OrderStatusHistory(
        tenant_id=order.tenant_id,
        order_id=order.id,
        from_stage=prev_stage,
        to_stage=order.current_stage,
        action="kargo_iptal",
        note=f"Kargo iptal · {ki.get('handler_name') or ''} {ki.get('takip_no') or ''}".strip()
             + ("" if shopify_ok else (f" · Shopify: {shopify_err}" if shopify_err else ""))
             + (" · SÜRAT'TA İPTAL EDİLMEDİ" if surat_uyari else ""),
        created_by=user.full_name or user.email,
    ))
    db.commit()
    return {
        "ok": True,
        "basit_ok": basit_ok,
        "shopify_ok": shopify_ok,
        "shopify_err": shopify_err,
        "silinen_gonderi": _silinen,
        "current_stage": order.current_stage,
        "surat_uyari": surat_uyari,
    }


@router.get("/qz-sertifika", response_model=None)
def qz_sertifika(user: User = Depends(get_current_user)):
    """QZ Tray'e tanıtılacak sertifika (yazıcı bilgisayarına override.crt)."""
    from app.services import qz_imza
    return Response(content=qz_imza.sertifika_pem(), media_type="text/plain")


class QzImzaIn(BaseModel):
    veri: str


@router.post("/qz-imza", response_model=dict)
def qz_imza_uret(body: QzImzaIn, user: User = Depends(get_current_user)):
    """QZ'nin gönderdiği isteği imzala.

    Özel anahtar sunucuda kalır; tarayıcıya asla verilmez. İmza olmadan QZ her
    baskıda izin soruyor ve "bu kararı hatırla" seçeneği çalışmıyor.
    """
    from app.services import qz_imza
    if len(body.veri) > 100_000:
        raise HTTPException(400, "İmzalanacak veri çok büyük")
    return {"imza": qz_imza.imzala(body.veri)}


@router.get("/order/{order_ref}/zpl")
def order_zpl(
    order_ref: str,
    tip: str = "kargo",     # kargo = Basit Kargo etiketi, adres = kendi etiketimiz
    dpi: int = 203,         # GX420t 203, GX430t 300
    w_mm: float = 0,        # etiket stoğunun ölçüsü
    h_mm: float = 0,
    doldur: bool = True,    # etiketi TAMAMEN doldur (oran korunmaz)
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Etiketi ZPL olarak ver — Zebra yazıcıya DOĞRUDAN gönderilir.

    Tarayıcının yazdırma hattı devreye girmediği için ne onay penceresi çıkar
    ne de ölçekleme ayarları çıktıyı bozar; barkod her zaman tam ölçüde basar.
    """
    from app.services.zpl_label import ZplError, pdf_to_zpl, svg_to_zpl

    order = _resolve_order(db, order_ref, user.tenant_id)
    try:
        if tip == "adres":
            pdf = label_pdf.render_label_pdf(order, _store_name(db, order))
            zpl = pdf_to_zpl(pdf, dpi=dpi, w_mm=w_mm or None, h_mm=h_mm or None, doldur=doldur)
        else:
            ki = order.kargo_info or {}
            if ki.get("provider") == "surat":
                # Sürat SVG değil PDF veriyor; adres etiketiyle aynı yoldan geçer.
                pdf = _surat_etiket_pdf(db, order, ki)
                zpl = pdf_to_zpl(pdf, dpi=dpi, w_mm=w_mm or None,
                                 h_mm=h_mm or None, doldur=doldur)
            else:
                if not ki.get("id"):
                    raise HTTPException(404, "Bu sipariş için kargo etiketi yok")
                svg = basit_kargo.get_label_svg(ki["id"])
                if not svg:
                    raise HTTPException(404, "Kargo etiketi alınamadı")
                zpl = svg_to_zpl(svg, dpi=dpi, w_mm=w_mm or None, h_mm=h_mm or None,
                                 doldur=doldur)
    except ZplError as e:
        raise HTTPException(400, f"ZPL üretilemedi: {e}") from e
    return Response(content=zpl, media_type="text/plain; charset=utf-8")


@router.get("/order/{order_ref}/kargo-label")
def kargo_label(
    order_ref: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Oluşturulmuş kargo etiketini yeniden getir (re-print).

    Basit Kargo'da SVG, Sürat'ta PDF döner — istemci Content-Type'a bakmalı.
    """
    order = _resolve_order(db, order_ref, user.tenant_id)
    ki = order.kargo_info or {}
    if ki.get("provider") == "surat":
        return Response(content=_surat_etiket_pdf(db, order, ki),
                        media_type="application/pdf")
    if not ki.get("id"):
        raise HTTPException(404, "Bu sipariş için kargo etiketi yok")
    svg = basit_kargo.get_label_svg(ki["id"])
    if not svg:
        raise HTTPException(502, "Etiket alınamadı")
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/order/{order_ref}/label")
def label(
    order_ref: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _resolve_order(db, order_ref, user.tenant_id)
    pdf = label_pdf.render_label_pdf(order, _store_name(db, order))
    filename = f"etiket_{order.order_number or order.id}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─── Paketleme Kuyrugu (Paket: paketleme yeniden tasarim) ─────────────
def _queue_filter(tenant_id):
    """Acik (gonderilmemis, iptal olmayan, tamamlanmamis) siparisler.

    Tanim order_scope'ta — stok ihtiyaci hesabi da AYNI olcutu kullaniyor."""
    from app.services.order_scope import acik_siparis_filtresi
    return acik_siparis_filtresi(tenant_id)


def _addr(raw: dict) -> dict:
    sa = (raw.get("shipping_address") or {})
    lines = raw.get("shipping_lines") or []
    kargo = (lines[0].get("title") if lines else None) or None
    a1 = sa.get("address1") or ""
    a2 = sa.get("address2") or ""
    full_addr = (a1 + (" " + a2 if a2 else "")).strip() or None
    return {
        "address": full_addr,
        "district": sa.get("city") or None,     # ilce
        "province": sa.get("province") or None,  # il
        "phone": sa.get("phone") or raw.get("phone") or None,
        "kargo_sirketi": kargo,
    }


def _customer_numune_url(li) -> str | None:
    """Kişiye özel siparişte müşterinin ilettiği numune görsel — line item
    properties içindeki ilk http(s) değeri (kisiye_ozel serileştirmesiyle aynı mantık)."""
    for p in li.properties or []:
        if not isinstance(p, dict):
            continue
        name = p.get("name") or ""
        val = p.get("value") or ""
        if name.startswith("_") or not val:
            continue
        if isinstance(val, str) and val.startswith("http"):
            return val
    return None


def _design_for_line_item(db, order, li, mi, adapter=None, kisiye_ids=None):
    """Paketleme görseli. Öncelik sırası:
    1) Kişiye özel ürün → müşterinin ilettiği numune görsel.
    2) Shopify ürün görseli (paketlemede tasarım değil, kutudaki/ürünün gerçek görseli).
    3) Son çare → tasarım küçük görseli (Shopify görseli hiç yoksa boş kalmasın)."""
    # 1) Kişiye özel → numune
    if kisiye_ids and li.product_id and str(li.product_id) in kisiye_ids:
        num = _customer_numune_url(li)
        if num:
            return num
    # 2) Shopify ürün görseli (lazy-fill: bir kez çekilip DB'ye yazılır)
    if li.product_image_url:
        return li.product_image_url
    if adapter is not None and li.product_id:
        try:
            img = adapter.get_product_image(li.product_id)
            if img:
                li.product_image_url = img   # DB'ye yaz (commit _order_payload sonunda)
                return img
        except Exception:
            pass
    # 3) Son çare — tasarım küçük görseli
    d = None
    if mi and mi.design_id:
        d = db.scalar(select(Design).where(Design.id == mi.design_id))
    if not d and li.assigned_design_id:
        d = db.scalar(select(Design).where(Design.id == li.assigned_design_id))
    if not d and li.product_id:
        d = db.scalar(
            select(Design).where(
                Design.store_id == order.store_id,
                Design.product_id == li.product_id,
            ).limit(1)
        )
    if d and d.file_path:
        return storage.get_thumbnail_url(d.file_path, d.file_format)
    return None


def _extract_model(li) -> str | None:
    # ÖNEMLİ: MoldItem.model kalip olusturulurken mold_planner.extract_phone_model ile
    # dolduruluyor. Paketleme uygunlugu (by_om) eslesmesi icin AYNI cikariciyi kullan,
    # aksi halde modeli raw.variant_title'da olan urunler eslesmiyor (basili kalipta olsa
    # bile "paketlemeye uygun" listesine girmiyor).
    from app.services.mold_planner import extract_phone_model
    return extract_phone_model(li)


def _kalip_kodu_for(db, li) -> str | None:
    """MoldItem varsa kalip kodu (+ ayni kod birden fazla kalipta ise part). Yoksa None."""
    mis = db.scalars(select(MoldItem).where(MoldItem.line_item_id == li.id)).all()
    if not mis:
        return None, None
    mi = mis[0]
    kod = mi.kalip_kodu or None
    # ayni kalip_kodu birden fazla farkli moldda ise part no (nadir)
    part = None
    if kod:
        molds = sorted({str(m.mold_id) for m in mis if m.kalip_kodu == kod})
        if len(molds) > 1:
            part = 1  # ilk; pratikte tek
    label = kod
    if kod and part:
        label = f"{kod} P{part}"
    return label, mi


def _order_payload(db, order) -> dict:
    raw = order.raw or {}
    info = _addr(raw)
    si = stage_defs.stage_info(order.current_stage or 1)
    # Shopify adapter'i siparis basina bir kez kur (urun gorseli lazy-fill icin)
    adapter = None
    try:
        store = db.scalar(select(Store).where(Store.id == order.store_id))
        if store:
            adapter = get_adapter(store)
    except Exception:
        adapter = None
    # Kişiye özel ürün ID'leri — bu ürünlerde numune görseli gösterilir
    kisiye_ids: set = set()
    if order.store_id:
        try:
            from app.routers.kisiye_ozel import _get_kop_product_ids
            kisiye_ids = _get_kop_product_ids(db, order.store_id)
        except Exception:
            kisiye_ids = set()
    # Couple ürünler: paketlemede İKİ modelin de görünmesi gerekiyor — kutuya
    # iki farklı kılıf giriyor. Tek sorguyla siparişin couple kalemlerini bul.
    _couple_pids: set = set()
    _pids = {str(li.product_id) for li in (order.line_items or []) if li.product_id}
    if _pids:
        from app.models import CoupleProduct as _CP
        _q = select(_CP.product_id).where(_CP.product_id.in_(_pids))
        if order.store_id:
            _q = _q.where(_CP.store_id == order.store_id)
        _couple_pids = {str(p) for (p,) in db.execute(_q).all()}

    items = []
    _img_filled = False
    for li in (order.line_items or []):
        kod_label, mi = _kalip_kodu_for(db, li)
        before = li.product_image_url
        thumb = _design_for_line_item(db, order, li, mi, adapter, kisiye_ids)
        if li.product_image_url and li.product_image_url != before:
            _img_filled = True
        _is_couple = bool(li.product_id) and str(li.product_id) in _couple_pids
        if _is_couple:
            from app.services.mold_planner import couple_modelleri
            _m1, _m2 = couple_modelleri(li)
        else:
            _m1, _m2 = _extract_model(li), None
        items.append({
            "line_item_id": str(li.id),
            "title": li.title,
            "model": _m1 or None,
            "model_2": _m2 or None,         # yalnizca couple'da dolu
            "is_couple": _is_couple,
            "quantity": li.quantity or 1,
            "kalip_kodu": kod_label,        # "A5" / "A5 P1" / None
            "thumbnail_url": thumb,         # gorsel ya da None
            # Hazırlanıp kenara ayrıldı mı (paketlemede görsele tıklayınca)
            "ayrildi": bool(getattr(li, "paketleme_ayrildi", False)),
        })
    if _img_filled:
        try:
            db.commit()
        except Exception:
            db.rollback()
    return {
        "id": str(order.id),
        "order_number": order.order_number,
        "name": order.name,
        "customer_name": order.customer_name,
        "address": info["address"],
        "district": info["district"],
        "province": info["province"],
        "phone": info["phone"],
        "kargo_sirketi": info["kargo_sirketi"],
        "note": order.note,
        "created_at_platform": order.created_at_platform.isoformat() if order.created_at_platform else None,
        "current_stage": order.current_stage or 1,
        "stage": si,                        # {no,key,label,icon}
        "progress_percent": stage_defs.progress_percent(order.current_stage or 1),
        "store_name": _store_name(db, order),
        "items": items,
        "total_units": sum((li.quantity or 1) for li in (order.line_items or [])),
    }


def _nm(s: str | None) -> str:
    from app.services import phone_models as _pm
    try:
        return _pm.normalize_key(s or "")
    except Exception:  # noqa: BLE001
        return (s or "").strip().upper()


def _printed_maps(db, tenant_id):
    """Tüm MoldItem'ları kalıbın print_status'üyle: line_item_id ve (order_no, model)
    bazında 'basıldı mı' listesi."""
    rows = db.execute(
        select(MoldItem.line_item_id, MoldItem.design_id, MoldItem.order_number,
               MoldItem.model, Mold.print_status, Mold.current_stage)
        .join(Mold, Mold.id == MoldItem.mold_id)
        .where(Mold.tenant_id == tenant_id)
    ).all()
    by_li: dict = {}
    by_om: dict = {}
    by_slot: dict = {}   # (line_item_id, design_id) -> [basildi?] — çift kılıf yarıları
    for li_id, did, onum, model, pstat, stage in rows:
        # Basili sayilir: print_status='basildi' (Baskici paneli) VEYA kalip stage 5
        # 'Tamamlandi' (asama akisindan tamamlanan kaliplar print_status'u basildi olmayabilir).
        printed = (pstat == "basildi") or (stage == 5)
        if li_id:
            by_li.setdefault(str(li_id), []).append(printed)
            by_slot.setdefault((str(li_id), str(did) if did else None), []).append(printed)
        if onum and model:
            by_om.setdefault((str(onum), _nm(model)), []).append(printed)
    return by_li, by_om, by_slot


def _accessory_ids(db, tenant_id) -> set:
    return {
        str(pid) for (pid,) in db.execute(
            select(AccessoryProduct.product_id)
            .join(Store, Store.id == AccessoryProduct.store_id)
            .where(Store.tenant_id == tenant_id, AccessoryProduct.product_id.isnot(None))
        ).all()
    }


def _couple_ids(db, tenant_id) -> set:
    """Çift kılıf (couple) ürün id'leri — bir kalem = 2 basılacak kılıf."""
    return {
        str(pid) for (pid,) in db.execute(
            select(CoupleProduct.product_id)
            .join(Store, Store.id == CoupleProduct.store_id)
            .where(Store.tenant_id == tenant_id, CoupleProduct.product_id.isnot(None))
        ).all()
    }


def _couple_tasarimlari(db, tenant_id) -> dict:
    """{product_id: (design_id_1, design_id_2)} — couple ürünün SABİT tasarımları.

    Kişiye özel OLMAYAN couple'da kalemin assigned_design_id alanları BOŞTUR;
    tasarımlar üründe tanımlıdır. Yalnız kaleme bakmak, kalıp eşleşmesinin hiç
    tutmamasına ve her iki yarının da "kalıba girmedi" görünmesine yol açıyordu.
    """
    out = {}
    for pid, d1, d2 in db.execute(
        select(CoupleProduct.product_id, CoupleProduct.design_id_1, CoupleProduct.design_id_2)
        .join(Store, Store.id == CoupleProduct.store_id)
        .where(Store.tenant_id == tenant_id, CoupleProduct.product_id.isnot(None))
    ).all():
        out[str(pid)] = (str(d1) if d1 else None, str(d2) if d2 else None)
    return out


def _kalem_uretildi(li, onum, by_li, by_om, acc_ids, couple_ids, by_slot,
                    couple_designs=None) -> bool | None:
    """Tek kalem üretildi mi. None = aksesuar (kalıp gerekmez, sayıma girmez).

    _order_ready ve _eksigi_var AYNI kuralı kullanmalı; kopyalanırsa biri
    düzeltilip diğeri eskide kalır.
    """
    if li.product_id and str(li.product_id) in acc_ids:
        return None                       # aksesuar — kalıp gerekmez
    _qty0 = max(1, int(getattr(li, "quantity", 1) or 1))
    _couple = bool(li.product_id and str(li.product_id) in couple_ids)

    if _couple:
        # ÇİFT KILIF: bir kalem = 2 ayrı kılıf, her yarı AYRI değerlendirilir.
        # Bir yarı ya elle hazır işaretli ya da kendi kalıbı basılmış olmalı.
        #
        # Tasarım kaynağı İKİ TÜRLÜ: kişiye özel couple'da kalemin kendi
        # atamaları, normal couple'da ürüne bağlı sabit tasarımlar. Yalnız
        # kaleme bakmak normal couple'da hep boş dönüyordu.
        _cp = (couple_designs or {}).get(str(li.product_id), (None, None))
        _did1 = str(li.assigned_design_id) if li.assigned_design_id else _cp[0]
        _did2 = str(li.assigned_design_id_2) if li.assigned_design_id_2 else _cp[1]
        for _manual, _did in (
            (getattr(li, "is_hazir", False), _did1),
            (getattr(li, "is_hazir_2", False), _did2),
        ):
            if _manual:
                continue
            _ms = by_slot.get((str(li.id), _did if _did else None))
            if not _ms or len(_ms) < _qty0 or not all(_ms):
                return False
        return True

    if getattr(li, "is_hazir", False):
        return True                       # elle hazır işaretli — üretildi sayılır
    # Kalıba eklenmemiş (hiç eklenmemiş YA DA tamamlanan kalıptan geri çıkarılmış)
    if not getattr(li, "is_kaliba_eklendi", False):
        return False
    ms = by_li.get(str(li.id))
    if not ms and onum:
        ms = by_om.get((onum, _nm(_extract_model(li))))
    _beklenen = _qty0 * (2 if _couple else 1)
    if not ms or len(ms) < _beklenen or not all(ms):
        return False
    return True


def _order_ready(order, by_li, by_om, acc_ids, couple_ids=None, by_slot=None,
                 couple_designs=None) -> bool:
    """Siparişin TÜM ürünleri 'üretildi' mi: ya basılı kalıpta, ya Hazır, ya aksesuar."""
    couple_ids = couple_ids or set()
    by_slot = by_slot or {}
    onum = str(order.order_number) if order.order_number is not None else None
    has_item = False
    for li in (order.line_items or []):
        has_item = True
        d = _kalem_uretildi(li, onum, by_li, by_om, acc_ids, couple_ids, by_slot, couple_designs)
        if d is False:
            return False
    return has_item


def _eksigi_var(order, by_li, by_om, acc_ids, couple_ids=None, by_slot=None,
                couple_designs=None) -> bool:
    """EN AZ BİR ürünü hazır ama HEPSİ değil — yani kargoya verilemez ama
    hazırlanan kılıflar kenara ayrılmalı.

    6 ürünlü siparişin 5'i hazırsa o 5 kılıf dükkanda ayrı durur; sistemde de
    görünsün diye bu filtre var.
    """
    couple_ids = couple_ids or set()
    by_slot = by_slot or {}
    onum = str(order.order_number) if order.order_number is not None else None
    hazir = eksik = 0
    for li in (order.line_items or []):
        d = _kalem_uretildi(li, onum, by_li, by_om, acc_ids, couple_ids, by_slot, couple_designs)
        if d is None:
            continue
        if d:
            hazir += 1
        else:
            eksik += 1
    return hazir > 0 and eksik > 0


class AyrildiIn(BaseModel):
    ayrildi: bool = True


@router.patch("/kalem/{line_item_id}/ayrildi", response_model=dict)
def kalem_ayrildi(line_item_id: uuid.UUID, body: AyrildiIn,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Kalemi "hazırlandı, kenara ayrıldı" olarak işaretle / işareti kaldır.

    Siparişin tamamı hazır olmasa da hazırlanan kılıflar dükkanda ayrı duruyor;
    bu işaret aynı ayrımı sistemde de gösteriyor.
    """
    li = db.scalar(
        select(LineItem).join(Order, Order.id == LineItem.order_id)
        .where(LineItem.id == line_item_id, Order.tenant_id == user.tenant_id)
    )
    if not li:
        raise HTTPException(404, "Kalem bulunamadı")
    li.paketleme_ayrildi = bool(body.ayrildi)
    db.commit()
    return {"ok": True, "line_item_id": str(line_item_id), "ayrildi": li.paketleme_ayrildi}


@router.get("/queue", response_model=dict)
def packaging_queue(
    index: int = 0,
    search: str | None = None,
    store_id: str | None = None,
    dealer_id: str | None = None,
    ready_only: bool = False,
    eksigi_olanlar: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Açık sipariş kuyruğu — EN ESKİDEN sıralı. Filtreler: sipariş no/müşteri arama,
    mağaza, bayi, ve 'paketlemeye uygun' (tüm ürünleri basılı kalıpta / hazır)."""
    flt = _queue_filter(user.tenant_id)
    s = (search or "").strip()
    if s:
        like = f"%{s}%"
        flt = flt & or_(
            Order.order_number.ilike(like), Order.name.ilike(like), Order.customer_name.ilike(like)
        )
    if store_id:
        try:
            flt = flt & (Order.store_id == uuid.UUID(store_id))
        except (ValueError, AttributeError):
            pass

    orders = db.scalars(
        select(Order).where(flt)
        .options(selectinload(Order.line_items))
        .order_by(asc(Order.created_at_platform), asc(Order.id))
    ).all()

    # Filtre menüleri: mağazalar + bayiler
    stores = [{"id": str(x.id), "name": x.name} for x in db.scalars(
        select(Store).where(
            Store.tenant_id == user.tenant_id, Store.platform != "bayii"
        ).order_by(Store.name)).all()]
    dealers = [{"id": str(x.id), "name": x.name} for x in db.scalars(
        select(Dealer).where(Dealer.tenant_id == user.tenant_id).order_by(Dealer.name)).all()]

    by_li = by_om = by_slot = None
    acc_ids: set = set()
    couple_ids: set = set()
    couple_designs: dict = {}
    if ready_only or eksigi_olanlar:
        by_li, by_om, by_slot = _printed_maps(db, user.tenant_id)
        acc_ids = _accessory_ids(db, user.tenant_id)
        couple_ids = _couple_ids(db, user.tenant_id)
        couple_designs = _couple_tasarimlari(db, user.tenant_id)

    _dealer = (dealer_id or "").strip()

    def _passes(o):
        if _dealer and str((o.raw or {}).get("dealer_id") or "") != _dealer:
            return False
        if ready_only and not _order_ready(o, by_li, by_om, acc_ids, couple_ids,
                                           by_slot, couple_designs):
            return False
        if eksigi_olanlar and not _eksigi_var(o, by_li, by_om, acc_ids, couple_ids,
                                              by_slot, couple_designs):
            return False
        return True

    filtered = [o for o in orders if _passes(o)] if (_dealer or ready_only or eksigi_olanlar) else orders
    total = len(filtered)
    base = {
        "stages": stage_defs.all_stages_payload(),
        "stores": stores,
        "dealers": dealers,
        "search": s or None,
        "store_id": store_id or None,
        "dealer_id": _dealer or None,
        "ready_only": ready_only,
        "eksigi_olanlar": eksigi_olanlar,
    }
    if total == 0:
        return {"total": 0, "index": 0, "order": None, **base}
    idx = max(0, min(index, total - 1))
    return {"total": total, "index": idx, "order": _order_payload(db, filtered[idx]), **base}
