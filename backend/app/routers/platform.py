"""
Platform yönetimi (white-label) — /api/platform/*

Yalnızca platform sahibi (is_platform_admin). Atölyeleri (tenant) oluştur/yönet:
plan, abonelik süresi, aktif/pasif, markalama. Kiralama iş modelinin çekirdeği.

is_platform_admin yalnızca DB'den elle verilir (kasıtlı — bu bayrağı atayan
endpoint YOK). İlk platform admini:
  UPDATE users SET is_platform_admin = true WHERE email = '...';
"""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete as sql_delete, func as sql_func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import require_platform_admin
from app.config import get_settings
from app.auth.schemas import slugify
from app.auth.security import create_access_token, hash_password
from app.database import get_db
from app.models import Order, Store, Tenant, User

router = APIRouter(
    prefix="/api/platform", tags=["platform"],
    dependencies=[Depends(require_platform_admin)],
)

# ⚠ AYRI ROUTER — üstteki blok TÜM uçlara Bearer başlığı şartı koyuyor. Tarayıcı
# <a href> ile başlık gönderemez, fetch+blob() ise GB'lık dosyayı belleğe alıp
# sekmeyi çökertir. Bu router yalnız TAM YEDEK İNDİRME için var ve kendi
# doğrulamasını imzalı jetonla yapıyor (bkz. download_full_backup).
indirme_router = APIRouter(prefix="/api/platform", tags=["platform"])

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def _unique_slug(db: Session, name: str) -> str:
    base = slugify(name) or "atolye"
    slug = base
    i = 1
    while db.scalar(select(Tenant).where(Tenant.slug == slug)):
        i += 1
        slug = f"{base}-{i}"
    return slug


def _ser_tenant(db: Session, t: Tenant) -> dict:
    user_count = db.scalar(
        select(sql_func.count(User.id)).where(User.tenant_id == t.id)
    ) or 0
    order_count = db.scalar(
        select(sql_func.count(Order.id)).where(Order.tenant_id == t.id)
    ) or 0
    # Onay ekraninda gostermek icin sahibin (owner) kayit meta bilgisi
    owner = db.scalar(
        select(User).where(User.tenant_id == t.id, User.role == "owner")
        .order_by(User.created_at).limit(1)
    )
    owner_email = owner.email if owner else None
    signup_ip = getattr(owner, "signup_ip", None) if owner else None
    signup_ua = getattr(owner, "signup_user_agent", None) if owner else None
    signup_device = None
    if signup_ua:
        from app.services.ua import summary as _ua_summary
        signup_device = _ua_summary(signup_ua)
    return {
        "id": str(t.id),
        "name": t.name,
        "slug": t.slug,
        "plan": t.plan,
        "is_active": t.is_active,
        "is_approved": bool(getattr(t, "is_approved", True)),
        "active_until": t.active_until.isoformat() if t.active_until else None,
        "logo_url": t.logo_url,
        "brand_color": t.brand_color,
        "app_name": t.app_name,
        "user_count": int(user_count),
        "order_count": int(order_count),
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "owner_email": owner_email,
        "signup_ip": signup_ip,
        "signup_device": signup_device,
    }


@router.get("/tenants", response_model=dict)
def list_tenants(user: User = Depends(require_platform_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(Tenant).order_by(Tenant.created_at.desc())).all()
    return {"items": [_ser_tenant(db, t) for t in rows]}


class CreateTenantRequest(BaseModel):
    tenant_name: str = Field(..., min_length=2, max_length=200)
    owner_email: EmailStr
    owner_password: str = Field(..., min_length=6, max_length=200)
    owner_name: str | None = None
    plan: str = "trial"
    active_until: date | None = None
    brand_color: str | None = None
    app_name: str | None = None


@router.post("/tenants", response_model=dict, status_code=201)
def create_tenant(
    req: CreateTenantRequest,
    user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    """Yeni atölye (tenant) + sahibi (owner) kullanıcı oluştur."""
    if db.scalar(select(User).where(User.email == req.owner_email.lower())):
        raise HTTPException(409, "Bu e-posta zaten kayıtlı.")
    if req.brand_color and not _HEX.match(req.brand_color):
        raise HTTPException(400, "Geçersiz renk (#rrggbb)")

    tenant = Tenant(
        name=req.tenant_name.strip(),
        slug=_unique_slug(db, req.tenant_name),
        plan=req.plan or "trial",
        is_active=True,
        active_until=req.active_until,
        brand_color=(req.brand_color or None),
        app_name=(req.app_name or "").strip()[:80] or None,
    )
    db.add(tenant)
    db.flush()

    owner = User(
        tenant_id=tenant.id,
        email=req.owner_email.lower(),
        password_hash=hash_password(req.owner_password),
        full_name=(req.owner_name or req.tenant_name).strip(),
        role="owner",
        is_active=True,
    )
    db.add(owner)
    db.commit()
    db.refresh(tenant)
    return _ser_tenant(db, tenant)


class UpdateTenantRequest(BaseModel):
    name: str | None = None
    plan: str | None = None
    is_active: bool | None = None
    is_approved: bool | None = None
    active_until: date | None = None
    clear_active_until: bool = False
    brand_color: str | None = None
    app_name: str | None = None


@router.patch("/tenants/{tenant_id}", response_model=dict)
def update_tenant(
    tenant_id: uuid.UUID,
    req: UpdateTenantRequest,
    user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    t = db.scalar(select(Tenant).where(Tenant.id == tenant_id))
    if not t:
        raise HTTPException(404, "Atölye bulunamadı")

    if req.name is not None:
        t.name = req.name.strip() or t.name
    if req.plan is not None:
        t.plan = req.plan.strip() or t.plan
    if req.is_active is not None:
        t.is_active = req.is_active
    if req.is_approved is not None:
        t.is_approved = req.is_approved
    if req.clear_active_until:
        t.active_until = None
    elif req.active_until is not None:
        t.active_until = req.active_until
    if req.brand_color is not None:
        c = req.brand_color.strip()
        if c and not _HEX.match(c):
            raise HTTPException(400, "Geçersiz renk (#rrggbb)")
        t.brand_color = c or None
    if req.app_name is not None:
        t.app_name = req.app_name.strip()[:80] or None

    db.commit()
    db.refresh(t)
    return _ser_tenant(db, t)


@router.delete("/tenants/{tenant_id}", response_model=dict)
def delete_tenant(
    tenant_id: uuid.UUID,
    user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    """Atölyeyi ve TÜM verisini kalıcı sil (CASCADE). Geri alınamaz.
    Kendi atölyen ve platform yöneticisi barındıran atölye silinemez."""
    t = db.scalar(select(Tenant).where(Tenant.id == tenant_id))
    if not t:
        raise HTTPException(404, "Atölye bulunamadı")
    if user.tenant_id == t.id:
        raise HTTPException(400, "Kendi atölyeni silemezsin")
    has_admin = db.scalar(
        select(sql_func.count(User.id)).where(
            User.tenant_id == t.id, User.is_platform_admin == True)  # noqa: E712
    ) or 0
    if has_admin:
        raise HTTPException(400, "Bu atölyede platform yöneticisi var; silinemez")

    import logging
    logging.getLogger("platform").warning(
        "DELETE TENANT: admin=%s -> tenant=%s (%s)", user.email, t.name, t.slug
    )
    # Tüm tenant_id FK'lari ondelete=CASCADE -> tek DELETE ile alt veri temizlenir
    db.execute(sql_delete(Tenant).where(Tenant.id == t.id))
    db.commit()
    # Dosyaları da temizle (best-effort)
    try:
        import shutil
        from app.services.storage import STORAGE_ROOT
        d = STORAGE_ROOT / "tenants" / str(t.id)
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True}


# ─── Atölye profilleri (kullanıcı) yönetimi ──────────────────
def _ser_user(u: User) -> dict:
    from app.services.ua import summary as _ua_summary
    _ua = getattr(u, "signup_user_agent", None)
    return {
        "id": str(u.id),
        "email": u.email,
        "full_name": u.full_name,
        "role": u.role,
        "is_active": u.is_active,
        "is_platform_admin": bool(getattr(u, "is_platform_admin", False)),
        "created_at": u.created_at.isoformat() if getattr(u, "created_at", None) else None,
        "signup_ip": getattr(u, "signup_ip", None),
        "signup_device": _ua_summary(_ua) if _ua else None,
        "signup_user_agent": _ua,
    }


@router.get("/tenants/{tenant_id}/users", response_model=dict)
def list_tenant_users(
    tenant_id: uuid.UUID,
    user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    """Atölyenin profilleri (kullanıcıları)."""
    t = db.scalar(select(Tenant).where(Tenant.id == tenant_id))
    if not t:
        raise HTTPException(404, "Atölye bulunamadı")
    rows = db.scalars(
        select(User).where(User.tenant_id == tenant_id).order_by(User.created_at)
    ).all()
    return {"items": [_ser_user(u) for u in rows]}


class PlatformUserUpdate(BaseModel):
    is_active: bool


@router.patch("/users/{user_id}", response_model=dict)
def platform_set_user_active(
    user_id: uuid.UUID,
    req: PlatformUserUpdate,
    user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    """Profilin girişini engelle / aç (is_active)."""
    u = db.scalar(select(User).where(User.id == user_id))
    if not u:
        raise HTTPException(404, "Profil bulunamadı")
    if req.is_active is False and (u.is_platform_admin or u.id == user.id):
        raise HTTPException(400, "Platform yöneticisinin / kendi girişin engellenemez")
    u.is_active = req.is_active
    db.commit()
    db.refresh(u)
    return _ser_user(u)


@router.delete("/users/{user_id}", response_model=dict)
def platform_delete_user(
    user_id: uuid.UUID,
    user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    """Profili sil. Platform yöneticisi, kendisi ve atölyenin tek sahibi silinemez."""
    u = db.scalar(select(User).where(User.id == user_id))
    if not u:
        raise HTTPException(404, "Profil bulunamadı")
    if u.id == user.id:
        raise HTTPException(400, "Kendi profilini silemezsin")
    if u.is_platform_admin:
        raise HTTPException(400, "Platform yöneticisi silinemez")
    if u.role == "owner":
        owner_count = db.scalar(
            select(sql_func.count(User.id)).where(
                User.tenant_id == u.tenant_id, User.role == "owner")
        ) or 0
        if owner_count <= 1:
            raise HTTPException(400, "Atölyenin tek sahibi silinemez")
    try:
        db.delete(u)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bu profile bağlı kayıtlar var; silmek yerine girişini engelle.")
    return {"ok": True}


@router.post("/users/{user_id}/impersonate", response_model=dict)
def impersonate_user(
    user_id: uuid.UUID,
    user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    """Platform admini bu profil olarak giriş yapsın — hedef kullanıcı için token üret.
    Hedef profil ve atölyesi aktif olmalı (yoksa token zaten anında geçersiz olur)."""
    u = db.scalar(select(User).where(User.id == user_id))
    if not u:
        raise HTTPException(404, "Profil bulunamadı")
    if not u.is_active:
        raise HTTPException(400, "Pasif profile giriş yapılamaz — önce girişini aç")
    t = db.scalar(select(Tenant).where(Tenant.id == u.tenant_id))
    if not t or not t.is_active:
        raise HTTPException(400, "Atölye pasif — önce aktifleştir")
    import logging
    logging.getLogger("platform").warning(
        "IMPERSONATE: admin=%s -> user=%s (tenant=%s)", user.email, u.email, t.slug
    )
    token = create_access_token(user_id=str(u.id), tenant_id=str(u.tenant_id), email=u.email)
    return {"access_token": token, "user_email": u.email, "tenant_name": t.name}


# ─── Veritabanı yedekleri (platform admin) ───────────────────

@router.get("/backups", response_model=dict)
def list_backups(user: User = Depends(require_platform_admin)):
    from app.services import backup
    return {"items": backup.list_backups(), "keep": backup.KEEP}


@router.post("/backups", response_model=dict)
def run_backup_now(user: User = Depends(require_platform_admin)):
    """Anlık yedek al (08:00 cron'u beklemeden)."""
    from app.services import backup
    try:
        return backup.run_backup()
    except backup.BackupError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/backups/{name}/download")
def download_backup(name: str, user: User = Depends(require_platform_admin)):
    from app.services import backup
    path = backup.backup_path(name)
    if not path:
        raise HTTPException(404, "Yedek bulunamadı")
    return FileResponse(str(path), media_type="application/gzip", filename=name)


# ─── TAM YEDEK (veritabanı + dosyalar) ────────────────────────────────────
# ⚠ Gecelik yedek yalnız veritabanını alıyor ve AYNI DİSKTE duruyor. Disk
# ölürse hem veri hem yedek gider; üstelik 6+ GB tasarım dosyası hiç
# yedeklenmiyordu. Tam yedek tek dosyada taşınır ve TEK KOMUTLA geri yüklenir.
@router.get("/tam-yedek", response_model=dict)
def list_full_backups(user: User = Depends(require_platform_admin)):
    from app.services import backup
    _yas = backup.tam_yedek_yasi_gun()
    return {
        "items": backup.list_full_backups(),
        "keep": backup.TAM_KEEP,
        "yas_gun": _yas,
        # Panel uyarıyı buna göre gösteriyor: dışarı indirilmemiş bir yedek,
        # olmayan yedektir — bayatladığı GÖRÜNMELİ.
        "bayat": (_yas is None or _yas > 7),
        "haric": list(backup.TAM_HARIC),
    }


@router.post("/tam-yedek", response_model=dict)
def run_full_backup_now(user: User = Depends(require_platform_admin)):
    """Tam yedek al. GB'larca veri kopyalar — dakikalar sürebilir."""
    from app.services import backup
    try:
        return backup.run_full_backup()
    except backup.BackupError as e:
        raise HTTPException(status_code=503, detail=str(e))


# ⚠ TAM YEDEK GB'LARCA. Tarayıcıdan indirmek için Authorization BAŞLIĞI
# kullanılamıyor: <a href> başlık gönderemez, fetch+blob() ise 5 GB'ı BELLEĞE
# alıp sekmeyi çökertir. Bu yüzden kısa ömürlü, TEK DOSYAYA bağlı imzalı bir
# jeton üretiliyor; tarayıcı doğrudan diske akıtıyor.
_JETON_SANIYE = 300


def _jeton_serici():
    from itsdangerous import URLSafeTimedSerializer
    return URLSafeTimedSerializer(get_settings().jwt_secret, salt="tam-yedek-indirme")


@router.post("/tam-yedek/{name}/indirme-jetonu", response_model=dict)
def full_backup_token(name: str, user: User = Depends(require_platform_admin)):
    from app.services import backup
    if not backup.full_backup_path(name):
        raise HTTPException(404, "Yedek bulunamadı")
    return {"jeton": _jeton_serici().dumps({"ad": name}), "saniye": _JETON_SANIYE}


@indirme_router.get("/tam-yedek/{name}/download")
def download_full_backup(name: str, jeton: str = ""):
    """İmzalı jetonla indirme (auth başlığı YOK — bkz. yukarıdaki not)."""
    from itsdangerous import BadSignature, SignatureExpired

    from app.services import backup

    try:
        veri = _jeton_serici().loads(jeton, max_age=_JETON_SANIYE)
    except SignatureExpired:
        raise HTTPException(410, "İndirme bağlantısının süresi doldu, tekrar deneyin.")
    except BadSignature:
        raise HTTPException(403, "Geçersiz indirme bağlantısı.")
    # Jeton TEK dosyaya bağlı: başka bir yedeğin adıyla kullanılamaz.
    if veri.get("ad") != name:
        raise HTTPException(403, "Bu bağlantı başka bir dosya için üretilmiş.")

    path = backup.full_backup_path(name)
    if not path:
        raise HTTPException(404, "Yedek bulunamadı")
    return FileResponse(str(path), media_type="application/x-tar", filename=name)
