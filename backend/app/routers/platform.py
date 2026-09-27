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
from decimal import Decimal

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
from app.models import AbonelikOdemesi, Order, Plan, PlatformAyari, Store, Tenant, User
from app.services import abonelik

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
        "plan_id": str(t.plan_id) if t.plan_id else None,
        "plan_ad": t.plan_kaydi.ad if t.plan_kaydi else None,
        "abonelik": abonelik.durum(t).sozluk(),
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
    plan_id: uuid.UUID | None = None
    active_until: date | None = None
    brand_color: str | None = None
    app_name: str | None = None


def _aktif_plan(db: Session, plan_id: uuid.UUID) -> Plan:
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(404, "Plan bulunamadı")
    if not plan.aktif:
        raise HTTPException(400, "Bu plan satışa kapalı; önce Planlar'dan açın.")
    return plan


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

    plan = _aktif_plan(db, req.plan_id) if req.plan_id else None
    tenant = Tenant(
        name=req.tenant_name.strip(),
        slug=_unique_slug(db, req.tenant_name),
        # Eski serbest metin alanı plan kodunu yansıtır (listelerde okunur kalsın)
        plan=plan.kod if plan else (req.plan or "trial"),
        plan_id=plan.id if plan else None,
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
    plan_id: uuid.UUID | None = None
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
    if req.plan_id is not None:
        plan = _aktif_plan(db, req.plan_id) if req.plan_id != t.plan_id else t.plan_kaydi
        t.plan_id = plan.id
        t.plan = plan.kod
    elif req.plan is not None:
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
    _disari = backup.disari_kopya_yasi_gun()
    _son = backup.son_indirme()
    return {
        "items": backup.list_full_backups(),
        "keep": backup.TAM_KEEP,
        "yas_gun": _yas,
        # ⚠ Bayatlık İNDİRMEYE göre: sunucuda duran arşiv disk ölünce onunla
        # gider. Dışarı indirilmemiş yedek, olmayan yedektir.
        "disari_yas_gun": _disari,
        "son_indirme": ({"ad": _son["ad"], "zaman": _son["zaman"].isoformat()}
                        if _son else None),
        "bayat": (_disari is None or _disari > backup.HATIRLATMA_ESIK_GUN),
        "esik_gun": backup.HATIRLATMA_ESIK_GUN,
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
    # Dışarı kopya takibi: hatırlatma "alındı mı" değil "İNDİRİLDİ mi"ye bakar.
    backup.indirme_kaydet(name)
    return FileResponse(str(path), media_type="application/x-tar", filename=name)



# ─── Planlar ve abonelik ödemeleri (Faz 3) ────────────────────────────────────
# Kiracıdan havaleyle para geldiğinde yönetici "Ödeme alındı" der: tutar o anın
# plan fiyatıyla dondurulur, abonelik uzar. Hesap kuralları services/abonelik.py.

def _ser_plan(db: Session, p: Plan) -> dict:
    kiraci = db.scalar(select(sql_func.count(Tenant.id)).where(Tenant.plan_id == p.id)) or 0
    return {
        "id": str(p.id), "kod": p.kod, "ad": p.ad,
        "aylik_ucret": str(p.aylik_ucret), "komisyon_orani": str(p.komisyon_orani),
        "moduller": list(p.moduller or []), "aktif": p.aktif, "sira": p.sira,
        "kiraci_sayisi": int(kiraci),
    }


@router.get("/plans", response_model=dict)
def list_plans(db: Session = Depends(get_db)):
    rows = db.scalars(select(Plan).order_by(Plan.sira, Plan.created_at)).all()
    return {
        "items": [_ser_plan(db, p) for p in rows],
        "moduller": [{"kod": k, "ad": v} for k, v in abonelik.MODUL_ADLARI.items()],
    }


class PlanRequest(BaseModel):
    ad: str | None = Field(None, min_length=1, max_length=80)
    aylik_ucret: Decimal | None = Field(None, ge=0, le=Decimal("1000000"))
    komisyon_orani: Decimal | None = Field(None, ge=0, le=100)
    moduller: list[str] | None = None
    aktif: bool | None = None


def _modulleri_dogrula(moduller: list[str]) -> list[str]:
    bilinmeyen = [m for m in moduller if m not in abonelik.MODUL_YETKILERI]
    if bilinmeyen:
        raise HTTPException(400, f"Bilinmeyen modül: {', '.join(bilinmeyen)}")
    if "magaza" not in moduller:
        # Mağaza paneli her planın tabanı: sipariş/ayar ekranları olmadan
        # kiracı kendi hesabını bile yönetemez.
        raise HTTPException(400, "Vitrin + mağaza paneli her planda olmalı.")
    # Sırayı sabitle (karşılaştırma ve görüntü tutarlılığı)
    return [m for m in abonelik.MODUL_YETKILERI if m in moduller]


@router.patch("/plans/{plan_id}", response_model=dict)
def update_plan(plan_id: uuid.UUID, req: PlanRequest, db: Session = Depends(get_db)):
    p = db.get(Plan, plan_id)
    if p is None:
        raise HTTPException(404, "Plan bulunamadı")
    if p.kod == "sahip" and (req.moduller is not None or req.aktif is False):
        # Platform sahibinin kendi atölyesi bu planda; modülü eksilirse ya da
        # plan kapanırsa kendi işletmesine kilitlenir.
        raise HTTPException(400, "Sahip planının modülleri ve durumu değiştirilemez.")
    if req.ad is not None:
        p.ad = req.ad.strip()
    if req.aylik_ucret is not None:
        p.aylik_ucret = req.aylik_ucret.quantize(Decimal("0.01"))
    if req.komisyon_orani is not None:
        p.komisyon_orani = req.komisyon_orani.quantize(Decimal("0.01"))
    if req.moduller is not None:
        p.moduller = _modulleri_dogrula(req.moduller)
    if req.aktif is not None:
        p.aktif = req.aktif
    db.commit()
    db.refresh(p)
    return _ser_plan(db, p)


class NewPlanRequest(PlanRequest):
    kod: str = Field(..., min_length=2, max_length=30, pattern=r"^[a-z0-9_-]+$")
    ad: str = Field(..., min_length=1, max_length=80)


@router.post("/plans", response_model=dict, status_code=201)
def create_plan(req: NewPlanRequest, db: Session = Depends(get_db)):
    if db.scalar(select(Plan).where(Plan.kod == req.kod)):
        raise HTTPException(409, "Bu kodla bir plan zaten var.")
    son_sira = db.scalar(select(sql_func.max(Plan.sira))) or 0
    p = Plan(
        kod=req.kod, ad=req.ad.strip(),
        aylik_ucret=(req.aylik_ucret or Decimal(0)).quantize(Decimal("0.01")),
        komisyon_orani=(req.komisyon_orani or Decimal(0)).quantize(Decimal("0.01")),
        moduller=_modulleri_dogrula(req.moduller or ["magaza"]),
        aktif=True if req.aktif is None else req.aktif, sira=son_sira + 1,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _ser_plan(db, p)


def _ser_odeme(o: AbonelikOdemesi, plan_ad: str | None = None) -> dict:
    return {
        "id": str(o.id), "tenant_id": str(o.tenant_id), "plan_ad": plan_ad,
        "donem_bas": o.donem_bas.isoformat(), "donem_bit": o.donem_bit.isoformat(),
        "ay_sayisi": o.ay_sayisi,
        "ciro_bas": o.ciro_bas.isoformat() if o.ciro_bas else None,
        "ciro_bit": o.ciro_bit.isoformat() if o.ciro_bit else None,
        "ciro": str(o.ciro), "siparis_sayisi": o.siparis_sayisi,
        "komisyon_orani": str(o.komisyon_orani), "komisyon": str(o.komisyon),
        "sabit_ucret": str(o.sabit_ucret), "toplam": str(o.toplam),
        "yontem": o.yontem, "durum": o.durum, "referans": o.referans, "not": o.not_,
        "odendi_at": o.odendi_at.isoformat() if o.odendi_at else None,
        "onceki_bitis": o.onceki_bitis.isoformat() if o.onceki_bitis else None,
        "yeni_bitis": o.yeni_bitis.isoformat() if o.yeni_bitis else None,
    }


def _tenant_or_404(db: Session, tenant_id: uuid.UUID) -> Tenant:
    t = db.get(Tenant, tenant_id)
    if t is None:
        raise HTTPException(404, "Atölye bulunamadı")
    return t


def _plan_adlari(db: Session) -> dict:
    return {p.id: p.ad for p in db.scalars(select(Plan)).all()}


@router.get("/tenants/{tenant_id}/abonelik", response_model=dict)
def tenant_abonelik(tenant_id: uuid.UUID, ay_sayisi: int = 1, db: Session = Depends(get_db)):
    """Kiracının plan/durum özeti, şimdi ödeme alınsa tahakkuk, ödeme geçmişi."""
    t = _tenant_or_404(db, tenant_id)
    try:
        tahakkuk = abonelik.tahakkuk_hesapla(db, t, ay_sayisi).sozluk()
        tahakkuk_hata = None
    except ValueError as e:
        tahakkuk, tahakkuk_hata = None, str(e)
    adlar = _plan_adlari(db)
    odemeler = db.scalars(
        select(AbonelikOdemesi).where(AbonelikOdemesi.tenant_id == t.id)
        .order_by(AbonelikOdemesi.created_at.desc()).limit(100)
    ).all()
    return {
        "tenant": _ser_tenant(db, t),
        "tahakkuk": tahakkuk, "tahakkuk_hata": tahakkuk_hata,
        "odemeler": [_ser_odeme(o, adlar.get(o.plan_id)) for o in odemeler],
    }


class OdemeRequest(BaseModel):
    yontem: str = Field("havale", pattern="^(havale|kart)$")
    ay_sayisi: int = Field(1, ge=1, le=24)
    # Önizlemede gösterilen toplam: arada sipariş düşer ya da plan fiyatı
    # değişirse yönetici görmediği bir tutarı onaylamış olmasın diye
    # karşılaştırılır.
    beklenen_toplam: Decimal
    referans: str | None = Field(None, max_length=200)
    not_: str | None = Field(None, alias="not", max_length=2000)


@router.post("/tenants/{tenant_id}/odemeler", response_model=dict, status_code=201)
def tenant_odeme_kaydet(
    tenant_id: uuid.UUID, req: OdemeRequest,
    user: User = Depends(require_platform_admin), db: Session = Depends(get_db),
):
    t = _tenant_or_404(db, tenant_id)
    try:
        onizleme = abonelik.tahakkuk_hesapla(db, t, req.ay_sayisi)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if onizleme.toplam != req.beklenen_toplam.quantize(Decimal("0.01")):
        raise HTTPException(409, f"Tutar değişti: güncel toplam {onizleme.toplam} TL. "
                                 "Ekranı yenileyip tekrar onaylayın.")
    odeme = abonelik.odeme_kaydet(
        db, t, yontem=req.yontem, ay_sayisi=req.ay_sayisi,
        referans=req.referans, not_=req.not_, kaydeden_id=user.id,
    )
    db.commit()
    db.refresh(odeme)
    return _ser_odeme(odeme, t.plan_kaydi.ad if t.plan_kaydi else None)


@router.post("/odemeler/{odeme_id}/iptal", response_model=dict)
def odeme_iptal(odeme_id: uuid.UUID, db: Session = Depends(get_db)):
    o = db.get(AbonelikOdemesi, odeme_id)
    if o is None:
        raise HTTPException(404, "Ödeme bulunamadı")
    try:
        abonelik.odeme_iptal(db, o)
    except ValueError as e:
        raise HTTPException(400, str(e))
    db.commit()
    return _ser_odeme(o)


@router.get("/tahakkuklar", response_model=dict)
def tahakkuklar(db: Session = Depends(get_db)):
    """Tüm kiracılar: durum ve şimdi ödeme alınsa tutar — "kim ne borçlu"."""
    satirlar = []
    for t in db.scalars(select(Tenant).order_by(Tenant.active_until.asc().nullslast())).all():
        try:
            th = abonelik.tahakkuk_hesapla(db, t)
        except ValueError:
            th = None
        satirlar.append({
            "tenant_id": str(t.id), "ad": t.app_name or t.name, "slug": t.slug,
            "plan_ad": t.plan_kaydi.ad if t.plan_kaydi else None,
            "active_until": t.active_until.isoformat() if t.active_until else None,
            "durum": abonelik.durum(t).sozluk(),
            "toplam": str(th.toplam) if th else None,
            "sabit_ucret": str(th.sabit_ucret) if th else None,
            "komisyon": str(th.komisyon) if th else None,
            "ciro": str(th.ciro) if th else None,
        })
    return {"items": satirlar}


HAVALE_ALANLARI = {"alici": 120, "banka": 80, "iban": 34, "aciklama": 300}


def havale_bilgisi(db: Session) -> dict:
    kayit = db.get(PlatformAyari, "havale")
    deger = (kayit.deger if kayit else None) or {}
    return {k: str(deger.get(k) or "") for k in HAVALE_ALANLARI}


@router.get("/ayarlar/havale", response_model=dict)
def get_havale(db: Session = Depends(get_db)):
    return havale_bilgisi(db)


@router.put("/ayarlar/havale", response_model=dict)
def put_havale(body: dict, db: Session = Depends(get_db)):
    deger = {k: str(body.get(k) or "").strip()[:n] for k, n in HAVALE_ALANLARI.items()}
    iban = deger["iban"].replace(" ", "").upper()
    if iban and not re.fullmatch(r"TR\d{24}", iban):
        raise HTTPException(400, "IBAN TR ile başlayan 26 karakter olmalı.")
    deger["iban"] = iban
    kayit = db.get(PlatformAyari, "havale")
    if kayit is None:
        db.add(PlatformAyari(anahtar="havale", deger=deger))
    else:
        kayit.deger = deger
    db.commit()
    return deger
