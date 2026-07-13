"""
Tasarım yönetimi — /api/designs/*
"""
from __future__ import annotations

import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import desc, func as sql_func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters import get_adapter
from app.auth.dependencies import get_current_user, require_any_permission
from app.database import get_db
from app.models import Design, KisiyeOzelProduct, LineItem, Order, Store, User
from app.services import storage

router = APIRouter(prefix="/api/designs", tags=["designs"],
    dependencies=[Depends(require_any_permission("tasarim", "kisiye_ozel", "aksesuar", "couple", "bayii"))],
)


def _serialize(d: Design) -> dict:
    return {
        "id": str(d.id),
        "store_id": str(d.store_id),
        "code": d.code,
        "name": d.name,
        "file_url": storage.get_design_url(d.file_path),
        "thumbnail_url": storage.get_thumbnail_url(d.file_path, d.file_format),
        "file_format": d.file_format,
        "file_size_bytes": d.file_size_bytes,
        "product_id": d.product_id,
        "product_title": d.product_title,
        "product_image_url": d.product_image_url,
        "kalip_tipi": d.kalip_tipi,
        "variant_title": d.variant_title,
        "birincil_renk": d.birincil_renk,
        "ikincil_renk": d.ikincil_renk,
        "ucuncu_renk": d.ucuncu_renk,
        "cmyk_hazirlanmis": d.cmyk_hazirlanmis,
        "is_kisiye_ozel": d.is_kisiye_ozel,
        "baski_dosyasi_yok": d.baski_dosyasi_yok,
        "notes": d.notes,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }


def _get_store(db: Session, store_id: uuid.UUID, tenant_id: uuid.UUID) -> Store:
    store = db.scalar(
        select(Store).where(Store.id == store_id, Store.tenant_id == tenant_id)
    )
    if not store:
        raise HTTPException(status_code=404, detail="Mağaza bulunamadı")
    return store


@router.get("", response_model=None)
def list_designs(
    store_id: uuid.UUID = Query(...),
    search: str | None = Query(None),
    no_product: bool = Query(False),
    no_kalip_tipi: bool = Query(False),
    no_renk: bool = Query(False),
    no_birincil: bool = Query(False),
    no_ikincil: bool = Query(False),
    no_ucuncu: bool = Query(False),
    cmyk_done: bool | None = Query(None),
    is_kisiye_ozel: bool | None = Query(None),
    baski_dosyasi_yok: bool | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(60, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_store(db, store_id, user.tenant_id)

    q = select(Design).where(Design.store_id == store_id)

    if search:
        like = f"%{search.lower()}%"
        q = q.where(
            (sql_func.lower(Design.code).like(like))
            | (sql_func.lower(Design.name).like(like))
            | (sql_func.lower(Design.product_title).like(like))
        )

    if no_product:
        q = q.where(Design.product_id.is_(None))
    if no_kalip_tipi:
        q = q.where(Design.kalip_tipi.is_(None))
    if no_birincil:
        q = q.where(Design.birincil_renk.is_(None))
    if no_ikincil:
        q = q.where(Design.ikincil_renk.is_(None))
    if no_ucuncu:
        q = q.where(Design.ucuncu_renk.is_(None))
    if no_renk:
        q = q.where(
            Design.birincil_renk.is_(None),
            Design.ikincil_renk.is_(None),
            Design.ucuncu_renk.is_(None),
        )
    if cmyk_done is not None:
        q = q.where(Design.cmyk_hazirlanmis == cmyk_done)
    if is_kisiye_ozel is not None:
        q = q.where(Design.is_kisiye_ozel == is_kisiye_ozel)
    if baski_dosyasi_yok is not None:
        q = q.where(Design.baski_dosyasi_yok == baski_dosyasi_yok)

    total = db.scalar(select(sql_func.count()).select_from(q.subquery())) or 0
    q = q.order_by(desc(Design.created_at)).limit(per_page).offset((page - 1) * per_page)
    rows = db.scalars(q).all()

    return {
        "items": [_serialize(d) for d in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if total else 0,
    }


@router.get("/_stats", response_model=None)
def stats(
    store_id: uuid.UUID = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_store(db, store_id, user.tenant_id)
    base = select(Design).where(Design.store_id == store_id)
    total = db.scalar(select(sql_func.count()).select_from(base.subquery())) or 0
    standart = db.scalar(select(sql_func.count()).where(Design.store_id == store_id, Design.is_kisiye_ozel.is_(False))) or 0
    ozel = db.scalar(select(sql_func.count()).where(Design.store_id == store_id, Design.is_kisiye_ozel.is_(True))) or 0
    with_product = db.scalar(select(sql_func.count()).where(Design.store_id == store_id, Design.product_id.isnot(None))) or 0
    cmyk_done = db.scalar(select(sql_func.count()).where(Design.store_id == store_id, Design.cmyk_hazirlanmis.is_(True))) or 0
    birincil = db.scalar(select(sql_func.count()).where(Design.store_id == store_id, Design.birincil_renk.isnot(None))) or 0
    ikincil = db.scalar(select(sql_func.count()).where(Design.store_id == store_id, Design.ikincil_renk.isnot(None))) or 0
    ucuncu = db.scalar(select(sql_func.count()).where(Design.store_id == store_id, Design.ucuncu_renk.isnot(None))) or 0

    return {
        "total": total, "standart": standart, "ozel": ozel,
        "with_product": with_product, "cmyk_done": cmyk_done,
        "renk_atanmis": {"birincil": birincil, "ikincil": ikincil, "ucuncu": ucuncu},
    }


@router.get("/_meta/unmatched-products", response_model=None)
def unmatched_products(
    store_id: uuid.UUID = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Siparişlerde geçen ama Design'a bağlanmamış ürünler (kalıp için eksikler)."""
    _get_store(db, store_id, user.tenant_id)
    # Bu mağazadaki siparişlerin line item'larından distinct product_id + sayaç + örnek başlık/görsel
    rows = db.execute(
        select(
            LineItem.product_id,
            sql_func.count(LineItem.id).label("cnt"),
            sql_func.max(LineItem.title).label("title"),
        )
        .join(Order, Order.id == LineItem.order_id)
        .where(
            Order.store_id == store_id,
            Order.tenant_id == user.tenant_id,
            LineItem.product_id.isnot(None),
        )
        .group_by(LineItem.product_id)
    ).all()

    # Zaten Design'a bağlı product_id'ler
    matched = set(
        str(p) for (p,) in db.execute(
            select(Design.product_id).where(
                Design.store_id == store_id,
                Design.product_id.isnot(None),
            )
        ).all()
    )
    # Kişiye özel ürünler katalog tasarımı gerektirmez -> hariç tut
    matched |= set(
        str(p) for (p,) in db.execute(
            select(KisiyeOzelProduct.product_id).where(
                KisiyeOzelProduct.store_id == store_id,
                KisiyeOzelProduct.product_id.isnot(None),
            )
        ).all()
    )

    items = []
    for pid, cnt, title in rows:
        if pid and str(pid) not in matched:
            items.append({"product_id": str(pid), "order_item_count": cnt, "sample_title": title})
    items.sort(key=lambda x: x["order_item_count"], reverse=True)
    return {"items": items, "total_unmatched": len(items)}


@router.get("/_meta/products", response_model=None)
def list_shopify_products(
    store_id: uuid.UUID = Query(...),
    search: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    store = _get_store(db, store_id, user.tenant_id)
    try:
        adapter = get_adapter(store)
        products = adapter.get_all_products(limit=250, search=search)
    except NotImplementedError:
        raise HTTPException(status_code=501, detail=f"{store.platform} adapter'ı ürün listelemeyi desteklemiyor")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ürünler alınamadı: {str(e)[:200]}") from e
    return {"items": products, "count": len(products)}


@router.get("/{design_id}", response_model=None)
def get_design(
    design_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    d = db.scalar(select(Design).where(Design.id == design_id, Design.tenant_id == user.tenant_id))
    if not d:
        raise HTTPException(status_code=404, detail="Tasarım bulunamadı")
    return _serialize(d)


@router.post("/{design_id}/print-file", response_model=None)
async def upload_print_file(
    design_id: uuid.UUID,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bu tasarıma temiz baskı dosyası yükle. Görsel ise CMYK PDF'e çevrilir (beyaz koruma);
    PDF ise doğrudan saklanır. Mockup/vitrin görseli (product_image_url) değişmez.
    'baskı dosyası yok' işareti kalkar → kalıp/baskı akışına girebilir."""
    import io as _io
    design = db.scalar(select(Design).where(Design.id == design_id, Design.tenant_id == user.tenant_id))
    if not design:
        raise HTTPException(status_code=404, detail="Tasarım bulunamadı")
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Boş dosya")
    if len(raw) > 50 * 1024 * 1024:
        raise HTTPException(413, "Dosya çok büyük (max 50 MB)")

    from app.services import product_studio as ps
    name = (file.filename or "").lower()
    if name.endswith(".pdf") or raw[:5] == b"%PDF-":
        pdf_bytes = raw   # zaten baskıya hazır PDF
    else:
        try:
            from PIL import Image as _Img
            img = _Img.open(_io.BytesIO(raw))
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "Görsel okunamadı")
        store = db.scalar(select(Store).where(Store.id == design.store_id))
        koff = int(((store.config or {}).get("cmyk_k_offset", 5) if store else 5) or 0)
        pdf_bytes = ps.make_print_pdf(img, k_offset_pct=koff)

    old = design.file_path
    saved = storage.save_design_file(user.tenant_id, design.id, pdf_bytes, f"{design.id}.pdf")
    # Eski designs/ dosyasını temizle; studio mockup'ı (aynı klasördeki baski.png) korunur
    if old and old != saved["relative_path"] and "/designs/" in old:
        storage.delete_design_file(old)
    design.file_path = saved["relative_path"]
    design.file_format = "pdf"
    design.file_size_bytes = saved["size"]
    design.baski_dosyasi_yok = False
    db.commit()
    db.refresh(design)
    return _serialize(design)


@router.post("", response_model=None, status_code=status.HTTP_201_CREATED)
async def create_design(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    store_id: uuid.UUID = Form(...),
    code: str = Form(..., min_length=1, max_length=50),
    name: str | None = Form(None),
    product_id: str | None = Form(None),
    product_title: str | None = Form(None),
    product_image_url: str | None = Form(None),
    kalip_tipi: str | None = Form(None),
    variant_title: str | None = Form(None),  # varyantlı ürün: müşterinin seçtiği değer (match)
    birincil_renk: str | None = Form(None),
    ikincil_renk: str | None = Form(None),
    ucuncu_renk: str | None = Form(None),
    is_kisiye_ozel: bool = Form(False),
    notes: str | None = Form(None),
    slot: int = Form(1),  # couple: 1 = 1. kılıf (assigned_design_id), 2 = 2. kılıf (assigned_design_id_2)
    # Opsiyonel: line item'a otomatik bağla
    line_item_id: uuid.UUID | None = Form(None),
    # Sync line item'ları yeniden oluşturunca id değişir; Shopify line item id (external_id)
    # STABİL kalır. id bulunamazsa buna düşülür -> "Line item bulunamadı" önlenir.
    line_item_external_id: str | None = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_store(db, store_id, user.tenant_id)

    if not storage.is_allowed_extension(file.filename or ""):
        raise HTTPException(
            status_code=400,
            detail=f"İzin verilen formatlar: {', '.join(sorted(storage.ALLOWED_EXTENSIONS))}",
        )

    file_data = await file.read()
    if len(file_data) > storage.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Dosya çok büyük (max {storage.MAX_FILE_SIZE // 1024 // 1024} MB)",
        )

    code_clean = code.strip()
    if not code_clean:
        raise HTTPException(status_code=400, detail="Tasarım kodu boş olamaz")

    # line_item_id verildiyse line_item'ı doğrula ve is_kisiye_ozel=True yap
    line_item = None
    if line_item_id or line_item_external_id:
        if line_item_id:
            line_item = db.scalar(
                select(LineItem).where(
                    LineItem.id == line_item_id,
                    LineItem.tenant_id == user.tenant_id,
                )
            )
        # id bulunamadı (ör. sync yeniden oluşturdu) -> stabil external_id ile dene
        if not line_item and line_item_external_id:
            line_item = db.scalar(
                select(LineItem).where(
                    LineItem.external_id == str(line_item_external_id),
                    LineItem.tenant_id == user.tenant_id,
                )
            )
        if not line_item:
            raise HTTPException(status_code=404, detail="Line item bulunamadı")
        is_kisiye_ozel = True  # otomatik

    def _none_if_empty(v: str | None) -> str | None:
        return v.strip() if v and v.strip() else None

    design = Design(
        tenant_id=user.tenant_id,
        store_id=store_id,
        code=code_clean,
        name=_none_if_empty(name),
        product_id=_none_if_empty(product_id),
        product_title=_none_if_empty(product_title),
        product_image_url=_none_if_empty(product_image_url),
        kalip_tipi=_none_if_empty(kalip_tipi),
        variant_title=_none_if_empty(variant_title),
        birincil_renk=_none_if_empty(birincil_renk),
        ikincil_renk=_none_if_empty(ikincil_renk),
        ucuncu_renk=_none_if_empty(ucuncu_renk),
        is_kisiye_ozel=is_kisiye_ozel,
        notes=_none_if_empty(notes),
        file_path="", file_format="", file_size_bytes=0,
    )
    db.add(design)

    try:
        db.flush()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=409, detail=f"Bu kod ({code_clean}) zaten kullanılıyor",
        ) from e

    try:
        file_info = storage.save_design_file(
            tenant_id=user.tenant_id, design_id=design.id,
            file_data=file_data, original_filename=file.filename or "design",
            skip_thumbnail=True,  # thumbnail arka planda uretilecek (hizli donus)
        )
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    except OSError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Dosya kaydedilemedi: {str(e)[:200]}") from e

    design.file_path = file_info["relative_path"]
    design.file_format = file_info["format"]
    design.file_size_bytes = file_info["size"]

    # Line item bağlanıyorsa (couple 2. kılıf için slot=2)
    if line_item:
        if slot == 2:
            line_item.assigned_design_id_2 = design.id
        else:
            line_item.assigned_design_id = design.id

    db.commit()
    db.refresh(design)

    # PDF thumbnail'i arka planda uret (yukleme bekletmesin)
    if file_info["format"] == "pdf":
        background_tasks.add_task(storage.generate_design_thumbnail, user.tenant_id, design.id)

    return _serialize(design)


@router.patch("/{design_id}", response_model=None)
async def update_design(
    design_id: uuid.UUID,
    code: str | None = Form(None),
    name: str | None = Form(None),
    product_id: str | None = Form(None),
    product_title: str | None = Form(None),
    product_image_url: str | None = Form(None),
    kalip_tipi: str | None = Form(None),
    variant_title: str | None = Form(None),
    birincil_renk: str | None = Form(None),
    ikincil_renk: str | None = Form(None),
    ucuncu_renk: str | None = Form(None),
    cmyk_hazirlanmis: bool | None = Form(None),
    is_kisiye_ozel: bool | None = Form(None),
    notes: str | None = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    design = db.scalar(select(Design).where(Design.id == design_id, Design.tenant_id == user.tenant_id))
    if not design:
        raise HTTPException(status_code=404, detail="Tasarım bulunamadı")

    if code is not None and code.strip():
        design.code = code.strip()
    for field, val in [
        ("name", name), ("product_id", product_id),
        ("product_title", product_title), ("product_image_url", product_image_url),
        ("kalip_tipi", kalip_tipi), ("variant_title", variant_title),
        ("birincil_renk", birincil_renk),
        ("ikincil_renk", ikincil_renk), ("ucuncu_renk", ucuncu_renk),
        ("notes", notes),
    ]:
        if val is not None:
            setattr(design, field, val.strip() if val.strip() else None)

    if cmyk_hazirlanmis is not None:
        design.cmyk_hazirlanmis = cmyk_hazirlanmis
    if is_kisiye_ozel is not None:
        design.is_kisiye_ozel = is_kisiye_ozel

    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail="Bu kod zaten kullanılıyor") from e

    db.refresh(design)
    return _serialize(design)


@router.delete("/{design_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_design(
    design_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    design = db.scalar(select(Design).where(Design.id == design_id, Design.tenant_id == user.tenant_id))
    if not design:
        raise HTTPException(status_code=404, detail="Tasarım bulunamadı")

    file_path = design.file_path
    db.delete(design)
    db.commit()

    if file_path:
        storage.delete_design_file(file_path)
    return None
