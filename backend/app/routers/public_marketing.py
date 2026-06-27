"""Pazarlama public sayfaları (auth YOK) — /api/pazarlama/*

- GET  /katil/{token}      → e-posta linkinden tek-tık abone (doğrulanmış)
- GET  /onay/{token}       → çift opt-in onayı (public form sonrası)
- GET  /cik/{token}        → abonelikten çık
- GET  /abone/{slug}       → public abonelik formu
- POST /abone/{slug}       → form gönderimi → onay maili
"""
from __future__ import annotations

import base64
from html import escape

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Tenant
from app.services import marketing

router = APIRouter(prefix="/api/pazarlama", tags=["pazarlama-public"])

_ACCENT = "#6d28d9"
_CONSENT_LABEL = "Kampanya, yeni ürün ve bilgilendirme e-postaları almayı kabul ediyorum."


def _client_ip(request: Request) -> str:
    cf = request.headers.get("cf-connecting-ip")
    if cf:
        return cf.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else ""


def _brand(tenant) -> tuple[str, str, str | None]:
    name = (getattr(tenant, "app_name", None) or getattr(tenant, "name", None) or "BERNZ")
    bc = (getattr(tenant, "brand_color", None) or "").strip() if tenant else ""
    if bc and not bc.startswith("#"):
        bc = "#" + bc
    accent = bc or _ACCENT
    logo = getattr(tenant, "logo_url", None) if tenant else None
    if logo and str(logo).startswith("/"):
        logo = get_settings().panel_base_url.rstrip("/") + str(logo)
    return name, accent, logo


def _page(tenant, *, title: str, message: str, icon: str = "✓",
          form_html: str = "", ok: bool = True) -> HTMLResponse:
    name, accent, logo = _brand(tenant)
    head = (
        f'<img src="{logo}" alt="{escape(name)}" style="height:30px;vertical-align:middle">'
        if logo else f'<span style="font-weight:700;font-size:18px;letter-spacing:.3px">{escape(name)}</span>'
    )
    html = f"""<!doctype html><html lang="tr"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title></head>
<body style="margin:0;background:#eef0f4;font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif">
<div style="max-width:460px;margin:7vh auto;background:#ffffff;border-radius:18px;overflow:hidden;box-shadow:0 6px 28px rgba(17,24,39,.10)">
  <div style="background:{accent};padding:18px 26px;color:#ffffff">{head}</div>
  <div style="padding:30px 28px;text-align:center;color:#374151">
    <div style="font-size:40px;line-height:1;margin-bottom:10px">{icon}</div>
    <h1 style="font-size:20px;color:#111827;margin:0 0 12px;font-weight:700">{escape(title)}</h1>
    <p style="font-size:15px;line-height:1.6;margin:0 0 16px">{message}</p>
    {form_html}
  </div>
</div></body></html>"""
    return HTMLResponse(html, status_code=200 if ok else 400)


def _unsub_line(sub, accent: str) -> str:
    return (f"<br><br><a href='{marketing.unsubscribe_url(sub)}' "
            f"style='color:#9ca3af;font-size:12px'>Abonelikten çık</a>")


@router.get("/katil/{token}", response_class=HTMLResponse)
def join(token: str, request: Request, db: Session = Depends(get_db)):
    data = marketing.consume_join_token(token)
    if not data:
        return _page(None, title="Geçersiz bağlantı", icon="⚠️", ok=False,
                     message="Bu abonelik bağlantısı geçersiz veya süresi dolmuş.")
    tenant = db.get(Tenant, data["t"])
    sub = marketing.subscribe_confirmed(db, data["t"], data["e"], data.get("n", ""),
                                        data.get("s", "order_mail"), _client_ip(request))
    if not sub:
        return _page(tenant, title="Olmadı", icon="⚠️", ok=False,
                     message="Abonelik tamamlanamadı. Lütfen tekrar deneyin.")
    _, accent, _ = _brand(tenant)
    return _page(tenant, title="Abone oldunuz 🎉", icon="🎉",
                 message="Artık kampanya ve yeni ürünlerden ilk siz haberdar olacaksınız."
                         + _unsub_line(sub, accent))


@router.get("/onay/{token}", response_class=HTMLResponse)
def confirm(token: str, request: Request, db: Session = Depends(get_db)):
    sub = marketing.confirm(db, token, _client_ip(request))
    if not sub:
        return _page(None, title="Geçersiz veya eski bağlantı", icon="⚠️", ok=False,
                     message="Onay bağlantısı geçersiz. Lütfen yeniden abone olmayı deneyin.")
    tenant = db.get(Tenant, sub.tenant_id)
    _, accent, _ = _brand(tenant)
    return _page(tenant, title="Aboneliğiniz onaylandı 🎉", icon="🎉",
                 message="Teşekkürler! Artık e-posta listemizdesiniz." + _unsub_line(sub, accent))


@router.get("/cik/{token}", response_class=HTMLResponse)
def unsubscribe(token: str, db: Session = Depends(get_db)):
    sub = marketing.unsubscribe(db, token)
    if not sub:
        return _page(None, title="Bağlantı bulunamadı", icon="⚠️", ok=False,
                     message="Bu abonelik bağlantısı geçersiz.")
    tenant = db.get(Tenant, sub.tenant_id)
    return _page(tenant, title="Abonelikten çıktınız", icon="👋",
                 message="Artık pazarlama e-postası almayacaksınız. "
                         "Fikrinizi değiştirirseniz dilediğiniz zaman tekrar abone olabilirsiniz.")


def _form_html(slug: str, accent: str) -> str:
    inp = ("width:100%;box-sizing:border-box;padding:11px 13px;margin:0 0 10px;"
           "border:1px solid #e5e7eb;border-radius:10px;font-size:15px")
    return f"""<form method="post" action="/api/pazarlama/abone/{escape(slug)}" style="text-align:left;margin-top:6px">
  <input name="name" placeholder="Adınız (opsiyonel)" style="{inp}">
  <input name="email" type="email" required placeholder="E-posta adresiniz" style="{inp}">
  <label style="display:flex;gap:8px;align-items:flex-start;font-size:12px;color:#6b7280;margin:6px 0 14px">
    <input type="checkbox" required style="margin-top:2px"> <span>{_CONSENT_LABEL}</span>
  </label>
  <button type="submit" style="width:100%;background:{accent};color:#fff;border:0;border-radius:10px;
    padding:13px;font-size:15px;font-weight:600;cursor:pointer">Abone Ol</button>
</form>"""


@router.get("/abone/{slug}", response_class=HTMLResponse)
def subscribe_form(slug: str, db: Session = Depends(get_db)):
    tenant = db.scalar(select(Tenant).where(Tenant.slug == slug))
    if not tenant:
        return _page(None, title="Bulunamadı", icon="⚠️", ok=False, message="Sayfa bulunamadı.")
    _, accent, _ = _brand(tenant)
    return _page(tenant, title="Kampanyalardan haberdar olun", icon="📩",
                 message="Yeni ürün ve kampanyalardan ilk siz haberdar olun.",
                 form_html=_form_html(slug, accent))


@router.post("/abone/{slug}", response_class=HTMLResponse)
def subscribe_submit(slug: str, request: Request, db: Session = Depends(get_db),
                     email: str = Form(""), name: str = Form("")):
    tenant = db.scalar(select(Tenant).where(Tenant.slug == slug))
    if not tenant:
        return _page(None, title="Bulunamadı", icon="⚠️", ok=False, message="Sayfa bulunamadı.")
    sub, st = marketing.subscribe_public(db, tenant.id, email, name, _client_ip(request))
    if st == "invalid":
        _, accent, _ = _brand(tenant)
        return _page(tenant, title="Geçersiz e-posta", icon="⚠️", ok=False,
                     message="Lütfen geçerli bir e-posta adresi girin.",
                     form_html=_form_html(slug, accent))
    if st == "already":
        return _page(tenant, title="Zaten abonesiniz", icon="✓",
                     message="Bu e-posta zaten listemizde. Teşekkürler!")
    return _page(tenant, title="Son bir adım 📩", icon="📩",
                 message="E-postanıza bir <b>onay bağlantısı</b> gönderdik. Aboneliğinizi "
                         "tamamlamak için lütfen onaylayın.<br><span style='font-size:13px;color:#9ca3af'>"
                         "(Gelen kutunuzu ve spam klasörünü kontrol edin.)</span>")


# ─── Açılma / tıklama takibi ─────────────────────────────────
_PIXEL = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")


@router.get("/a/{send_id}")
def track_open(send_id: str, db: Session = Depends(get_db)):
    """Açılma takibi — görünmez 1x1 GIF döner."""
    try:
        marketing.record_open(db, send_id)
    except Exception:  # noqa: BLE001 — takip asla isteği bozmasın
        pass
    return Response(content=_PIXEL, media_type="image/gif",
                    headers={"Cache-Control": "no-store, no-cache, must-revalidate"})


@router.get("/t/{send_id}")
def track_click(send_id: str, db: Session = Depends(get_db)):
    """Tıklama takibi — kaydeder, kampanya buton linkine yönlendirir."""
    url = None
    try:
        url = marketing.record_click(db, send_id)
    except Exception:  # noqa: BLE001
        pass
    return RedirectResponse(url or (get_settings().panel_base_url or "/"), status_code=302)
