"""
FastAPI dependency'leri:

- get_current_user: JWT'den user'ı çek, DB'den hidrate et
- get_current_tenant: user.tenant_id'den tenant'ı çek
- TenantContext: request.state.tenant_id (DB sorgularında kullanmak için)

Korumalı endpoint:
    @router.get("/orders")
    def list_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        return db.scalars(select(Order).where(Order.tenant_id == user.tenant_id)).all()
"""
from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import safe_decode
from app.database import get_db
from app.models import Tenant, User

# HTTPBearer header'dan "Authorization: Bearer <token>" alır
_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Authentication required") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


# ─── Bayi hesabinin erisebilecegi yollar (VARSAYILAN: KAPALI) ───
# Bayi kullanicisi yonetimle AYNI tenant icinde. Yalnizca izin adini ayirmak
# YETMEZ: izin ISTEMEYEN, sadece get_current_user ile korunan her uc bayiye de
# acik kalir. Denetimde /api/notifications, /api/search, /api/stores ve
# /api/dashboard/* bu yuzden bayi token'iyla 200 donuyordu.
#
# Kapiyi get_current_user'in ICINE koyuyoruz: her korumali uc zaten buradan
# geciyor, dolayisiyla yarin eklenen bir yonetim ucu de kendiliginden kapali
# olur. Router basina Depends eklemek bu garantiyi vermezdi.
BAYI_IZINLI_ONEKLER = (
    "/api/bayii/",        # portalin kendi uclari
    "/api/push/",         # kendi cihazina bildirim aboneligi
)
# ⚠ /api/auth/ ARTIK ONEKLE ACIK DEGIL. Eskiden "/api/auth/" tumuyle bayiye
# aciktı ve yalnız iki uç yasak listesindeydi: yarın /api/auth altina eklenen
# herhangi bir personel ucu (ör. baska kullanici adina islem) bayiye OTOMATIK
# acilacakti. Artik varsayilan RED; bayinin gercekten kullandigi uclar tek tek
# yaziliyor. Token GEREKTIRMEYEN uclar (login, logout, 2fa/verify-login,
# passkey girisi, sifre sifirlama) bu kapiya hic ugramaz.
# Yeni bir /api/auth ucu eklenince scripts/bayii_portal_test.py onu
# SINIFLANDIRMADAN gecmez.
BAYI_IZINLI_TAM = (
    "/api/health",
    "/api/version",
    "/api/auth/me",               # kendi profili (GET/PATCH)
    "/api/auth/verify-password",  # bayi ayarlarinda sifre dogrulama
    "/api/auth/change-password",  # kendi sifresi
    "/api/auth/refresh",          # oturumu tazele (bayi de kullanir)
)
# Varsayilan RED zaten kapatiyor; burada acikca durmalari, biri onegi geri
# acarsa bu ikisinin YINE kapali kalmasi icin. Profil degistirme personel
# ozelligi: bayi buradan personel token'i alabilirdi.
BAYI_YASAK_TAM = (
    "/api/auth/profiles",
    "/api/auth/select-profile",
)


def _bayi_kapisi(user: User, yol: str) -> None:
    """Bayi hesabi yalnizca portal yollarina girebilir."""
    if not user.dealer_id:
        return
    if yol in BAYI_YASAK_TAM:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bayi hesabi bu bolume erisemez",
        )
    if yol in BAYI_IZINLI_TAM or yol.startswith(BAYI_IZINLI_ONEKLER):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Bayi hesabi bu bolume erisemez",
    )


def _abonelik_kapisi(user: User, request: Request, db: Session) -> None:
    """Kiralama kapısı: plan kısıtı + ödeme durumu, HER istekte.

    İKİ AÇIK KAPATILIR
      1. Kiracı eskiden yalnız GİRİŞTE kontrol ediliyordu. Elle askıya alınan
         ya da süresi dolan bir kiracının elindeki token (7 gün geçerli) çoğu
         uçta çalışmaya devam ediyordu. Artık her istekte bakılıyor.
      2. owner/yönetici "her şey" demekti; kiracı kendi mağazasının owner'ı
         olduğu için Basic planla üretim ve bayi modüllerine girebilirdi.
         Artık yetki, PLANIN açtığıyla kesişiyor (bkz. permissions.py).

    Platform yöneticisi hiçbir zaman kısıtlanmaz: sahip, "sahip" planı
    yanlışlıkla silinse bile kendi atölyesine kilitlenip kalmasın.
    """
    from app.services import abonelik

    if getattr(user, "is_platform_admin", False):
        user._plan_yetkileri = None
        return

    tenant = db.get(Tenant, user.tenant_id)
    if tenant is None or not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hesabınız askıya alındı. Lütfen bizimle iletişime geçin.",
        )

    user._plan_yetkileri = abonelik.izinli_yetkiler(tenant)
    durum = abonelik.durum(tenant)
    request.state.abonelik = durum

    # Salt-okunur dönemde yalnız OKUMA serbest. Ödeme yapabilmesi ve oturumunu
    # yönetebilmesi için birkaç yol açık kalır — yoksa borcunu ödeyemez.
    if not durum.yazma_izni and request.method not in ("GET", "HEAD", "OPTIONS"):
        yol = request.url.path
        if not yol.startswith(ABONELIK_YAZMA_ACIK):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=durum.mesaj or "Aboneliğiniz aktif değil — panel salt-okunur.",
            )


# Salt-okunur dönemde bile yazılabilen yollar: oturum yönetimi, ödeme ve
# bildirim aboneliği. Başka hiçbir şey değiştirilemez.
ABONELIK_YAZMA_ACIK = (
    "/api/auth/",
    "/api/abonelik/",
    "/api/push/",
)


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """JWT'yi doğrula, user'ı döndür. Token yok/geçersizse 401."""
    if not creds or creds.scheme.lower() != "bearer":
        raise _unauthorized("Bearer token gerekli")

    payload = safe_decode(creds.credentials)
    if not payload:
        raise _unauthorized("Geçersiz veya süresi dolmuş token")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise _unauthorized("Token'da kullanıcı bilgisi yok")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise _unauthorized("Geçersiz token formatı") from None

    user = db.scalar(select(User).where(User.id == user_id))
    if not user or not user.is_active:
        raise _unauthorized("Kullanıcı bulunamadı veya pasif")

    # OTURUM İPTALİ: parola değişimi/sıfırlama ve 2FA kapatma bu damgayı ileri
    # alır; ondan ÖNCE üretilmiş token'lar ölür. Olmadan, parola değiştirmek
    # çalınmış bir oturumu düşürmüyordu (JWT 7 gün geçerli, geri alma yok).
    gecerli_from = getattr(user, "sessions_valid_from", None)
    if gecerli_from is not None:
        iat = payload.get("iat")
        # Damga saniyeye indirilir: `iat` tam saniye oldugu icin mikrosaniyeli
        # bir damga, ayni saniyedeki gecerli token'lari da olduruyordu.
        _sinir = int(gecerli_from.timestamp())
        if not isinstance(iat, (int, float)) or iat < _sinir:
            raise _unauthorized("Oturum sonlandırıldı — tekrar giriş yapın")

    _bayi_kapisi(user, request.url.path)
    _abonelik_kapisi(user, request, db)

    # Tenant izolasyonu için request.state'e yaz — log/audit için faydalı
    request.state.user_id = user.id
    request.state.tenant_id = user.tenant_id

    return user


def get_current_tenant(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Tenant:
    """Aktif tenant'ı döndür. Abonelik biti, aktif değil vs. kontrolü burada."""
    tenant = db.scalar(select(Tenant).where(Tenant.id == user.tenant_id))
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant bulunamadı",
        )
    if not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hesap pasif. Lütfen yöneticiyle iletişime geçin.",
        )
    # active_until kontrolü ileride: abonelik bittiyse read-only mod vs.
    return tenant


def require_role(*allowed: str):
    """Belirli rolleri zorla. Örn: require_role("owner")."""
    def dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Bu işlem için yetki yok. Gerekli rol: {', '.join(allowed)}",
            )
        return user
    return dep


def require_platform_admin(user: User = Depends(get_current_user)) -> User:
    """Platform sahibi (cross-tenant white-label yönetimi). Sadece is_platform_admin."""
    if not getattr(user, "is_platform_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu işlem yalnızca platform yöneticisine açıktır.",
        )
    return user


from app.auth import permissions as _perms  # esnek yetki sistemi


def require_permission(perm: str):
    """Panel yetkisi zorla. Yonetici her zaman gecer. Orn: require_permission('kalip')."""
    def dep(user: User = Depends(get_current_user)) -> User:
        if not _perms.has_permission(user, perm):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Bu panel icin yetkin yok: {perm}",
            )
        return user
    return dep


def require_any_permission(*perms: str):
    """Verilen yetkilerden EN AZ BIRI yeterli (paneller-arasi paylasilan endpoint'ler).
    Orn: require_any_permission('siparisler', 'bayii')."""
    def dep(user: User = Depends(get_current_user)) -> User:
        if not _perms.has_any_permission(user, perms):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Bu islem icin yetkin yok: {' / '.join(perms)}",
            )
        return user
    return dep
