"""
Sürat Kargo entegrasyonu — OrtakBarkodOlustur

Gönderi oluşturur, takip no + barkod (base64 PDF) döndürür.
Canlı: https://api01.suratkargo.com.tr/api/OrtakBarkodOlustur
Test : https://api02.suratkargo.com.tr/api/OrtakBarkodOlustur
"""
from __future__ import annotations

import re
import requests

from app.config import settings

CANLI_URL = "https://api01.suratkargo.com.tr/api/OrtakBarkodOlustur"
TEST_URL = "https://api02.suratkargo.com.tr/api/OrtakBarkodOlustur"

# KargoTuru: 1 Dosya / 2 Mi / 3 Koli  → telefon kılıfı = Mi (2)
KARGO_TURU_MI = 2


def _normalize_phone(raw: str | None) -> str:
    """Telefonu 10 haneli '5...' formatına getir (Surat: 5 ile baslamali)."""
    if not raw:
        return ""
    d = re.sub(r"\D", "", raw)          # sadece rakam
    if d.startswith("90") and len(d) == 12:
        d = d[2:]                        # 90 5xx... -> 5xx...
    if d.startswith("0") and len(d) == 11:
        d = d[1:]                        # 0 5xx... -> 5xx...
    return d                              # 10 hane '5...' beklenir


def _addr_parts(raw: dict) -> dict:
    sa = raw.get("shipping_address") or {}
    a1 = (sa.get("address1") or "").strip()
    a2 = (sa.get("address2") or "").strip()
    adres = (a1 + (" " + a2 if a2 else "")).strip()
    ad = (sa.get("first_name") or "").strip()
    soyad = (sa.get("last_name") or "").strip()
    kisi = (ad + " " + soyad).strip() or (sa.get("name") or "").strip()
    return {
        "kisi": kisi,
        "adres": adres,
        "il": (sa.get("province") or "").strip(),
        "ilce": (sa.get("city") or "").strip(),
        "telefon": _normalize_phone(sa.get("phone") or raw.get("phone")),
        "email": (raw.get("email") or raw.get("contact_email") or "").strip(),
    }


def create_shipment(
    order_raw: dict,
    *,
    ozel_kargo_takip_no: str,
    canli: bool = True,
    kullanici_adi: str | None = None,
    sifre: str | None = None,
) -> dict:
    """
    Sürat'a gönderi oluşturur.
    Returns: {ok, takip_no, barkod_base64, message, raw_response}
    """
    ka = kullanici_adi or settings.surat_kullanici_adi
    sf = sifre or settings.surat_sifre
    if not ka or not sf:
        return {"ok": False, "message": "Sürat kullanıcı adı/şifre tanımlı değil (.env)"}

    info = _addr_parts(order_raw)
    if not info["telefon"] or len(info["telefon"]) < 10:
        return {"ok": False, "message": f"Geçersiz telefon: '{info['telefon']}'"}
    if not info["il"] or not info["ilce"] or not info["adres"]:
        return {"ok": False, "message": "Eksik adres bilgisi (il/ilçe/adres)"}

    payload = {
        "KullaniciAdi": ka,
        "Sifre": sf,
        "Gonderi": {
            "KisiKurum": info["kisi"] or "Alıcı",
            "AliciAdresi": info["adres"],
            "Il": info["il"],
            "Ilce": info["ilce"],
            "TelefonCep": info["telefon"],
            "Email": info["email"],
            "KargoTuru": KARGO_TURU_MI,     # Mi
            "OdemeTipi": 1,                  # Peşin (gönderici öder)
            "IrsaliyeSeriNo": "",
            "IrsaliyeSiraNo": "",
            "ReferansNo": "",
            "OzelKargoTakipNo": str(ozel_kargo_takip_no)[:50],
            "Adet": 1,
            "BirimDesi": 1,                  # Mi: desi=1
            "BirimKg": 1,                    # Mi: kg=1
            "KargoIcerigi": "",
            "KapidanOdemeTahsilatTipi": 0,
            "KapidanOdemeTutari": "0",
            "EkHizmetler": "",
            "TasimaSekli": 1,                # Kara yolu
            "TeslimSekli": 1,                # Adrese teslim
            "SevkAdresi": "",
            "GonderiSekli": 0,               # Standart
            "TeslimSubeKodu": "",
            "Pazaryerimi": 0,
            "EntegrasyonFirmasi": "",
            "Iademi": 0,
        },
    }

    url = CANLI_URL if canli else TEST_URL
    try:
        r = requests.post(url, json=payload, timeout=30)
    except Exception as e:
        return {"ok": False, "message": f"Bağlantı hatası: {str(e)[:150]}"}

    try:
        data = r.json()
    except Exception:
        return {"ok": False, "message": f"Geçersiz yanıt (HTTP {r.status_code}): {r.text[:200]}"}

    # Basarili response: isError False, Message '015'/'016', KargoTakipNo dolu
    is_error = data.get("isError", data.get("IsError", True))
    message = str(data.get("Message", ""))
    takip_no = data.get("KargoTakipNo") or ""
    barkod = data.get("Barcode")
    barkod_b64 = barkod[0] if isinstance(barkod, list) and barkod else (barkod if isinstance(barkod, str) else None)

    # basarili kodlar: 013,014,015,016 (barkod iletildi/gonderildi)
    basarili = (not is_error) and (message in ("013", "014", "015", "016") or bool(takip_no))
    return {
        "ok": bool(basarili),
        "takip_no": takip_no,
        "barkod_base64": barkod_b64,
        "message": message,
        "http_status": r.status_code,
        "raw_response": data if not basarili else None,  # hata ayiklama icin
    }
