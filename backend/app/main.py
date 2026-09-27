"""Baskıcı SaaS — FastAPI ana uygulama."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.auth.router import router as auth_router
from app.routers.passkey import router as passkey_router
from app.config import get_settings
from app.routers.designs import router as designs_router
from app.routers.studio import router as studio_router
from app.routers import aski
from app.routers.kisiye_ozel import router as kisiye_ozel_router
from app.routers.accessories import router as accessories_router
from app.routers.users import router as users_router
from app.routers.bayii_portal import router as bayii_portal_router
from app.routers.dealers import router as dealers_router
from app.routers.couple import router as couple_router
from app.routers.order_detail import router as order_detail_router
from app.routers.orders import router as orders_router
from app.routers.notifications import router as notifications_router
from app.routers.molds import router as molds_router
from app.routers.phone_models import router as phone_models_router
from app.routers.stock import router as stock_router
from app.routers.packaging import router as packaging_router
from app.routers.dashboard import router as dashboard_router
from app.routers.public_shop import router as public_shop_router
from app.routers.public_tracker import router as public_tracker_router
from app.routers.public_support import router as public_support_router
from app.routers.ozel_seri import router as ozel_seri_router
from app.routers.public_adres_degisim import router as public_adres_degisim_router
from app.routers.public_approval import router as public_approval_router
from app.routers.public_model_degisim import router as public_model_degisim_router
from app.routers.public_instagram import router as public_instagram_router
from app.routers.public_instagram import pages_router as public_pages_router
from app.routers.webhooks import router as webhooks_router
from app.routers.marketing import router as marketing_router
from app.routers.public_marketing import router as public_marketing_router
from app.routers.platform import router as platform_router
from app.routers.platform import indirme_router as platform_indirme_router
from app.routers.support import router as support_router
from app.routers.templates import router as templates_router
from app.routers.pipeline import router as pipeline_router
from app.routers.telafiler import router as telafiler_router
from app.routers.settings import router as tenant_settings_router
from app.routers.shortcuts import router as shortcuts_router
from app.routers.stores import router as stores_router
from app.routers.catalog import router as catalog_router
from app.routers.birfatura import router as birfatura_router
from app.routers.entegrasyon import router as entegrasyon_router
from app.routers.discounts import router as discounts_router
from app.routers.blog import router as blog_router
from app.routers.design_requests import router as design_requests_router
from app.routers.customers import router as customers_router
from app.routers.analytics import router as analytics_router
from app.routers.checkout_admin import router as checkout_admin_router
from app.routers.design_studio import router as design_studio_router
from app.routers.store_activity import router as store_activity_router
from app.routers.store_settings import router as store_settings_router
from app.routers.audit import router as audit_router
from app.routers.search import router as search_router
from app.routers.push import router as push_router
from app.routers.instagram import router as instagram_router
from app.scheduler import shutdown_scheduler, start_scheduler
from app.services import storage as storage_service

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[baskici] starting up (env={settings.env})")
    storage_service.ensure_storage_root()
    print(f"[baskici] storage root: {storage_service.STORAGE_ROOT}")
    try:
        start_scheduler()
        print("[baskici] scheduler started (hourly sync)")
    except Exception as e:
        print(f"[baskici] scheduler start failed: {e}")
    yield
    shutdown_scheduler()
    print("[baskici] shutting down")


# Üretimde /docs, /redoc ve /openapi.json KAPALI: tüm uçların, şemaların ve
# alan adlarının haritasını saldırgana vermek gereksiz kolaylıktır
# (yetkilendirme zaten koruyor ama keşfi zorlaştırmak savunmanın parçası).
_is_prod = settings.env == "production"
app = FastAPI(
    title="Baskıcı SaaS API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
    openapi_url=None if _is_prod else "/openapi.json",
)


@app.exception_handler(RequestValidationError)
async def dogrulama_hatasi(request: Request, exc: RequestValidationError):
    """İstek doğrulama hatalarını LOG'A yaz + istemciye OKUNUR mesaj ver.

    Öntanımlı davranışta gövde `{"detail": [ {...}, ... ]}` yani DİZİ olur;
    vitrin `detail`i metin bekleyip "Ödeme başlatılamadı" gibi genel bir
    mesaja düşüyor ve asıl sebep (hangi alan?) hiçbir yerde görünmüyordu.
    Artık hem sunucu günlüğünde hem yanıtta alan adı ve sebebi yazıyor.
    """
    parcalar = []
    for h in exc.errors():
        yol = ".".join(str(x) for x in h.get("loc", ()) if x != "body")
        parcalar.append(f"{yol}: {h.get('msg', 'geçersiz')}")
    ozet = " · ".join(parcalar) or "Geçersiz istek"
    # Gövdeli isteklerde gövdenin KÜNYESİNİ de yaz. Bir bayi, formu eksiksiz
    # doldurduğu hâlde "model/adet/kanal/ad_soyad: Field required" aldı; sebep
    # gövdenin sunucuya BOŞ ulaşmasıydı (araya giren service worker, iOS'ta
    # dosyalı isteğin gövdesini düşürüyordu). Bu satır olmadan "alan eksik" ile
    # "gövde hiç gelmemiş" ayırt edilemiyor.
    kunye = ""
    if request.method in ("POST", "PUT", "PATCH"):
        kunye = " | ct=%s len=%s ua=%s" % (
            request.headers.get("content-type", "-"),
            request.headers.get("content-length", "-"),
            (request.headers.get("user-agent", "-") or "-")[:120],
        )
    logging.getLogger("dogrulama").warning(
        "dogrulama hatasi %s %s → %s%s",
        request.method, request.url.path, ozet, kunye)
    return JSONResponse(status_code=422, content={"detail": ozet, "alanlar": exc.errors()})


@app.exception_handler(Exception)
async def beklenmeyen_hata(request: Request, exc: Exception):
    """Yakalanmayan her istisna → log + Telegram/bildirim + kullanıcıya sade mesaj.

    ⚠ NEDEN: eskiden beklenmeyen bir hata yalnız log dosyasına düşüyordu ve o
    dosyayı kimse okumuyordu. Bir müşteri sayfası patlasa, müşteri şikayet
    edene kadar haberimiz olmuyordu.

    İstemciye ayrıntı SIZDIRILMAZ: yığın izi ve iç mesaj yalnız bize gider.
    """
    logging.getLogger("hata").exception(
        "beklenmeyen hata %s %s", request.method, request.url.path)
    try:
        from app.services import hata_uyari
        hata_uyari.bildir(request.method, request.url.path, exc)
    except Exception:  # noqa: BLE001 — uyarı yanıtı BOZMAZ
        pass
    return JSONResponse(
        status_code=500,
        content={"detail": "Beklenmeyen bir hata oluştu. Ekip bilgilendirildi."})


@app.middleware("http")
async def security_headers(request, call_next):
    """API yanıtlarına güvenlik başlıkları — JSON'un tarayıcıda script gibi
    yorumlanmasını ve API'nin iframe'e gömülmesini engeller."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    if _is_prod:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response

# Native kabuk (Capacitor) sayfayi KENDI origin'inde acar: iOS'ta
# capacitor://localhost, Android'de http://localhost. Bu origin'ler listede
# olmazsa uygulamanin HER istegi CORS'a takilir (preflight 400).
#
# GUVENLIGI ZAYIFLATMAZ: bu API kimligi CEREZLE degil Authorization: Bearer
# basligiyla dogruluyor. CORS bir kimlik sinir degil; origin eklemek gecerli
# token olmadan hicbir sey acmaz ve CSRF'e yol vermez (CSRF ortam kimligi,
# yani cerez ister). Tarayici bu semalara zaten gezinemez.
_IZINLI_ORIGIN = [
    settings.frontend_url,
    "capacitor://localhost",   # iOS native kabuk
    "http://localhost",        # Android native kabuk
    "https://localhost",       # Android (https semasi secilirse)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_IZINLI_ORIGIN,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Routers ──────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(passkey_router)
app.include_router(stores_router)
app.include_router(orders_router)
app.include_router(order_detail_router)
app.include_router(shortcuts_router)
app.include_router(pipeline_router)
app.include_router(telafiler_router)
app.include_router(designs_router)
app.include_router(studio_router)
app.include_router(tenant_settings_router)
app.include_router(kisiye_ozel_router)
app.include_router(accessories_router)
app.include_router(users_router)
app.include_router(dealers_router)
app.include_router(bayii_portal_router)
app.include_router(couple_router)
app.include_router(notifications_router)
app.include_router(molds_router)
app.include_router(templates_router)
app.include_router(phone_models_router)
app.include_router(stock_router)
app.include_router(packaging_router)
app.include_router(dashboard_router)
app.include_router(public_tracker_router)
app.include_router(public_support_router)
app.include_router(ozel_seri_router)
app.include_router(public_adres_degisim_router)
app.include_router(public_approval_router)
app.include_router(public_model_degisim_router)
app.include_router(public_instagram_router)
app.include_router(public_pages_router)
app.include_router(webhooks_router)
app.include_router(marketing_router)
app.include_router(public_marketing_router)
app.include_router(platform_router)
app.include_router(platform_indirme_router)
app.include_router(support_router)
app.include_router(aski.router)
app.include_router(audit_router)
app.include_router(search_router)
app.include_router(push_router)
app.include_router(instagram_router)
app.include_router(catalog_router)
app.include_router(discounts_router)
app.include_router(blog_router)
app.include_router(design_requests_router)
app.include_router(customers_router)
app.include_router(analytics_router)
app.include_router(checkout_admin_router)
app.include_router(store_settings_router)
app.include_router(store_activity_router)
app.include_router(design_studio_router)
app.include_router(public_shop_router)
app.include_router(entegrasyon_router)
app.include_router(birfatura_router)


# ─── Rota golgeleme denetimi ──────────────────────────────────
def _golgelenen_rotalari_bul() -> list[str]:
    """'/orders/{order_id}' gibi parametreli bir rota, KENDINDEN SONRA tanimlanan
    '/orders/_takip-bekleyen' gibi sabit rotalari yutar — FastAPI rotalari tanim
    sirasina gore eslestirir. Istek parametreli rotaya duser, sabit segment UUID
    olarak ayristirilmaya calisilir ve uc sessizce hata verir.

    Bu tam olarak yasandi: toplu takip listesi haftalarca bos gorundu.
    Uygulama acilirken sinanir; bulunan her cakisma acik hatayla dusurulur."""
    import re

    param = re.compile(r"\{[^}]+\}")
    onceki: list[tuple[str, set[str], list[str]]] = []  # (yol, metodlar, parcalar)
    sorunlar: list[str] = []

    for r in app.router.routes:
        yol = getattr(r, "path", None)
        metodlar = getattr(r, "methods", None)
        if not yol or not metodlar:
            continue
        parcalar = yol.strip("/").split("/")
        for e_yol, e_metodlar, e_parcalar in onceki:
            if not (metodlar & e_metodlar) or len(parcalar) != len(e_parcalar):
                continue
            # Onceki rota bunu yutuyor mu? Her segmentte ya birebir ayni,
            # ya da onceki tarafta parametre olmali. Sabit-sabit farki varsa yutmaz.
            yutar = param_var = False
            for p, e in zip(parcalar, e_parcalar):
                if param.fullmatch(e):
                    param_var = True
                elif p != e:
                    break
            else:
                yutar = param_var
            # Yalnizca bu rota sabitken sorun: parametreli rota digerini gizler.
            if yutar and not any(param.search(p) for p in parcalar):
                sorunlar.append(
                    f"{sorted(metodlar)[0]} {yol}  <-- once tanimlanan {e_yol} bunu golgeliyor"
                )
                break
        onceki.append((yol, metodlar, parcalar))
    return sorunlar


_golge = _golgelenen_rotalari_bul()
if _golge:
    raise RuntimeError(
        "Golgelenen rota(lar) var — sabit yollar parametreli yoldan ONCE tanimlanmali:\n  "
        + "\n  ".join(_golge)
    )


# ─── Guvenli statik servis (SVG/HTML XSS korumasi) ────────────
from starlette.responses import Response as _Resp

class SafeStaticFiles(StaticFiles):
    """SVG/HTML/XML gibi tarayicida script calistirabilen dosyalari
    inline yerine attachment olarak + siki guvenlik basliklariyla servis eder.
    Resimler (png/jpg/jpeg/gif/webp) normal inline gosterilir.

    NEDEN ONEMLI: /storage PANEL alan adindan da servis ediliyor ve panel
    JWT'yi localStorage'da tutuyor. Inline calisan bir SVG, yoneticinin
    oturumunu calabilir. Musteri tasarim yukleme ucu SVG'yi KIMLIKSIZ kabul
    ediyor (vektorel baski kaynagi) — yani dosyayi koyan saldirgan olabilir.

    2026-09-08'DE YANDI: uzanti `Path(path).suffix` ile hesaplaniyordu ama
    `Path` bu modulde hic import edilmemisti. Her istekte NameError firliyor,
    ciplak `except Exception` yutuyor, uzanti bos kaliyordu — koruma yazildigi
    gunden beri CALISMIYORDU. Bu yuzden artik:
      · uzanti hicbir sey firlatmayan saf string islemiyle bulunuyor,
      · except YOK (guvenlik kontrolu sessizce basarisiz olmamali),
      · davranis scripts/statik_xss_test.py ile sinaniyor (kod degil, BASLIK).
    """
    _RISKY_EXT = {"svg", "html", "htm", "xml", "xhtml", "svgz"}

    async def get_response(self, path: str, scope):
        resp = await super().get_response(path, scope)
        ad = str(path).rsplit("/", 1)[-1]
        ext = ad.rsplit(".", 1)[-1].lower() if "." in ad else ""
        # Tum statik dosyalara temel guvenlik basliklari
        resp.headers["X-Content-Type-Options"] = "nosniff"
        # Görseller içerik adresli (dosya adında image_id) → değişmez.
        # Uzun önbellek: aynı görsel bir daha sunucuya dönmez, CDN'de kalır.
        if ext in ("jpg", "jpeg", "png", "webp", "gif"):
            resp.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
        if ext in self._RISKY_EXT:
            # Tarayicida CALISTIRMA — indir + CSP ile script engelle
            resp.headers["Content-Disposition"] = "attachment"
            resp.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
            resp.headers["Content-Type"] = "application/octet-stream"
        return resp


# ─── Static files (tasarım dosyaları) ─────────────────────────
storage_service.ensure_storage_root()
app.mount(
    "/storage",
    SafeStaticFiles(directory=str(storage_service.STORAGE_ROOT)),
    name="storage",
)

# ─── Destek görselleri (public /uploads) ──────────────────────
from app.services import uploads as uploads_service
uploads_service.ensure_upload_root()
app.mount(
    "/uploads",
    SafeStaticFiles(directory=str(uploads_service.UPLOAD_ROOT)),
    name="uploads",
)


# ─── Health ───────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"ok": True, "env": settings.env}


@app.get("/api/version")
async def version():
    return {"version": app.version}
