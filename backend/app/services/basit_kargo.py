"""Basit Kargo entegrasyonu — https://basitkargo.com/api

Çoklu kargo agregatörü (PTT, MNG, Yurtiçi, Aras, Sürat + Ekonomik/Hızlı).
Sürat'in yerine: tek POST ile gönderi+barkod oluşturur, gerçek kargo firması
takip no'sunu (handlerShipmentCode) ve SVG etiketi döndürür.

Auth: Bearer token (.env BASIT_KARGO_TOKEN). Token yoksa is_configured()=False.
Adres ayrıştırma (il/ilçe/telefon) surat.py helper'larından gelir.
"""
from __future__ import annotations

import requests

from app.config import get_settings
from app.services import surat as _surat  # adres ayrıştırma (il/ilçe/telefon) yeniden kullanımı

BASE_URL = "https://basitkargo.com/api"

# handlerCode -> Shopify'a/UI'a yazılacak görünen firma adı
HANDLER_NAMES: dict[str, str] = {
    "ECONOMIC": "Basit Kargo (Ekonomik)",
    "FAST": "Basit Kargo (Hızlı)",
    "PTT": "PTT Kargo",
    "MNG": "MNG Kargo",
    "YURTICI": "Yurtiçi Kargo",
    "ARAS": "Aras Kargo",
    "SURAT": "Sürat Kargo",
    "SELF_PTT": "PTT Kargo",
    "SELF_MNG": "MNG Kargo",
    "SELF_YURTICI": "Yurtiçi Kargo",
    "SELF_ARAS": "Aras Kargo",
    "SELF_SURAT": "Sürat Kargo",
}
DEFAULT_HANDLER = "ECONOMIC"


def is_configured() -> bool:
    return bool(get_settings().basit_kargo_token)


def handler_name(code: str | None) -> str:
    return HANDLER_NAMES.get((code or "").upper(), code or "Kargo")


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {get_settings().basit_kargo_token}",
        "Content-Type": "application/json",
    }


def create_shipment(
    order_raw: dict,
    *,
    handler_code: str = DEFAULT_HANDLER,
    order_code: str = "",
    il_override: str | None = None,
    ilce_override: str | None = None,
) -> dict:
    """Gönderi + barkod oluştur (POST /v2/order/barcode).

    Returns: {ok, id, barcode, takip_no, handler_code, handler_name, status,
              label_svg, message, raw}
    İlçe çözülemezse {ok:False, ilce_eksik:True}.
    """
    s = get_settings()
    if not is_configured():
        return {"ok": False, "message": "Basit Kargo token tanımlı değil (.env BASIT_KARGO_TOKEN)"}

    info = _surat._addr_parts(order_raw)
    # Manuel il/ilçe (adresten çözülemeyen siparişlerde panelden seçilir)
    if il_override and ilce_override:
        from app.services import tr_iller
        info["il"] = tr_iller.resolve_il(il_override) or il_override
        info["ilce"] = ilce_override
        info["ilce_gecerli"] = True
    if not info["telefon"] or len(info["telefon"]) < 10:
        return {"ok": False, "message": f"Geçersiz telefon: '{info['telefon']}'"}
    if not info["il"] or not info["adres"]:
        return {"ok": False, "message": "Eksik adres bilgisi (il/adres)"}
    if not info.get("ilce_gecerli"):
        return {
            "ok": False,
            "message": f"İlçe belirlenemedi (il={info['il']}, ilçe='{info['ilce']}'). "
                       "Adreste ilçe yok — Shopify'da ilçeyi düzeltip tekrar deneyin.",
            "ilce_eksik": True,
            "il": info["il"],
        }

    hc = (handler_code or DEFAULT_HANDLER).upper()
    body = {
        "handlerCode": hc,
        "type": "OUTGOING",
        "content": {
            "name": str(order_code or "Sipariş")[:60],
            "code": str(order_code or "")[:40],
            # Telefon kılıfı — küçük koli (desi ~1)
            "packages": [{"height": 10, "width": 15, "depth": 5, "weight": 1}],
        },
        "client": {
            "name": info["kisi"] or "Alıcı",
            "phone": info["telefon"],
            "city": info["il"],
            "town": info["ilce"],
            "address": info["adres"],
            "email": info.get("email") or "",
        },
    }
    if s.basit_kargo_address_id:
        body["addressId"] = s.basit_kargo_address_id
    if s.basit_kargo_brand_id:
        body["brandId"] = s.basit_kargo_brand_id

    try:
        # (connect, read): barkod + etiket üretimi yavaş olabilir -> read timeout uzun.
        r = requests.post(
            f"{BASE_URL}/v2/order/barcode", json=body, headers=_headers(), timeout=(10, 90)
        )
    except requests.exceptions.Timeout:
        # Basit Kargo zamanında yanıt vermedi. Gönderi onların tarafında OLUŞMUŞ olabilir;
        # tekrar denemeden ÖNCE Basit Kargo panelinden kontrol et (çift kargo riski).
        return {"ok": False, "timeout": True, "message": (
            "Basit Kargo zamanında yanıt vermedi (zaman aşımı). Gönderi oluşmuş olabilir — "
            "tekrar denemeden önce Basit Kargo panelinden bu siparişi kontrol et (çift kargo riski)."
        )}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": f"Bağlantı hatası: {str(e)[:180]}"}

    if r.status_code not in (200, 201):
        # Sebebi tespit edebilmek icin GONDERDIGIMIZ veriyi de logla. 500 cogu zaman
        # onlarin tarafidir ama bazen hatali/eksik alan da 500 olarak doner; govde ve
        # payload yan yana olmadan ayirt edilemiyor.
        try:
            import json as _json
            import logging as _lg
            _icerik = dict(body.get("content") or {})
            _lg.getLogger("basit_kargo").warning(
                "[basit-kargo] HTTP %s | handler=%s | yanit=%s | gonderilen=%s",
                r.status_code, body.get("handlerCode"), (r.text or "")[:400],
                _json.dumps({k: _icerik.get(k) for k in
                             ("name", "city", "town", "address", "phone", "email")},
                            ensure_ascii=False)[:400],
            )
        except Exception:  # noqa: BLE001
            pass
        return {"ok": False, "message": f"Basit Kargo HTTP {r.status_code}: {r.text[:200]}"}

    d = r.json() if r.content else {}
    if d.get("validationFailed"):
        return {"ok": False, "message": f"Doğrulama hatası: {d.get('validationMessage') or 'geçersiz adres/alan'}", "raw": d}

    bk_id = d.get("id")
    if not bk_id:
        return {"ok": False, "message": "Gönderi oluşturulamadı (id boş)", "raw": d}

    takip = d.get("handlerShipmentCode") or d.get("barcode") or ""
    # handlerShipmentCode boş geldiyse barkod sorgusuyla tamamlamayı dene
    if not takip and d.get("barcode"):
        det = get_by_barcode(d["barcode"])
        if det:
            takip = det.get("handlerShipmentCode") or d.get("barcode") or ""

    return {
        "ok": True,
        "id": bk_id,
        "barcode": d.get("barcode"),
        "takip_no": takip,
        "handler_code": hc,
        "handler_name": handler_name(hc),
        "status": d.get("status"),
        "label_svg": get_label_svg(bk_id),
        "message": "OK",
    }


def get_label_svg(bk_id: str | None) -> str | None:
    """Gönderi etiketini SVG olarak çek (GET /label/svg/{id})."""
    if not bk_id:
        return None
    try:
        r = requests.get(f"{BASE_URL}/label/svg/{bk_id}", headers=_headers(), timeout=30)
        if r.status_code == 200 and r.text.strip().startswith("<"):
            return r.text
    except Exception:  # noqa: BLE001
        pass
    return None


def get_by_barcode(barcode: str) -> dict | None:
    """Barkoda göre gönderi detayı (GET /v2/order/barcode/{barcode})."""
    try:
        r = requests.get(f"{BASE_URL}/v2/order/barcode/{barcode}", headers=_headers(), timeout=20)
        if r.status_code == 200:
            return r.json()
    except Exception:  # noqa: BLE001
        pass
    return None


def cancel(barcode: str) -> bool:
    """Kargo kodunu iptal et (DELETE /order/barcode/{barcode}) — şubeye teslimden önce."""
    try:
        r = requests.delete(f"{BASE_URL}/order/barcode/{barcode}", headers=_headers(), timeout=20)
        return r.status_code in (200, 204)
    except Exception:  # noqa: BLE001
        return False


def test_connection() -> tuple[bool, str]:
    """Token geçerli mi (GET /firm/address)."""
    if not is_configured():
        return (False, "Token tanımlı değil")
    try:
        r = requests.get(f"{BASE_URL}/firm/address", headers=_headers(), timeout=15)
        if r.status_code == 200:
            return (True, "Bağlantı çalışıyor")
        if r.status_code in (401, 403):
            return (False, "Token geçersiz/yetkisiz")
        return (False, f"HTTP {r.status_code}")
    except Exception as e:  # noqa: BLE001
        return (False, str(e)[:120])
