"""
Sürat Kargo entegrasyonu — OrtakBarkodOlustur

Gönderi oluşturur, takip no + barkod (base64 PDF) döndürür.
Canlı: https://api01.suratkargo.com.tr/api/OrtakBarkodOlustur
Test : https://api02.suratkargo.com.tr/api/OrtakBarkodOlustur
"""
from __future__ import annotations

import re
import requests

from app.config import get_settings
from app.services import tr_iller

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


def _split_il_ilce(province: str, city: str) -> tuple[str, str]:
    """Shopify il/ilce tutarsiz gelebilir. Olasi durumlar:
    - province='Gaziantep', city='Sahinbey'         -> (il, ilce)
    - province=None, city='Gaziantep/Sahinbey'       -> '/' ile bol
    - province=None, city='Gaziantep'                -> il=ilce=Gaziantep
    """
    province = (province or "").strip()
    city = (city or "").strip()
    # city icinde ayirici varsa (/, -, ,) -> il/ilce
    for sep in ("/", " - ", " / ", ",", "-"):
        if sep in city:
            parts = [x.strip() for x in city.split(sep) if x.strip()]
            if len(parts) >= 2:
                return parts[0], parts[1]
    if province and city:
        return province, city
    if province and not city:
        return province, province
    if city and not province:
        return city, city
    return "", ""


def _addr_parts(raw: dict) -> dict:
    sa = raw.get("shipping_address") or {}
    a1 = (sa.get("address1") or "").strip()
    a2 = (sa.get("address2") or "").strip()
    adres = (a1 + (" " + a2 if a2 else "")).strip()
    ad = (sa.get("first_name") or "").strip()
    soyad = (sa.get("last_name") or "").strip()
    kisi = (ad + " " + soyad).strip() or (sa.get("name") or "").strip()
    il, ilce = _split_il_ilce(sa.get("province"), sa.get("city"))
    # ilce gecerli mi? degilse adres metninden cikarmayi dene
    if il and not tr_iller.gecerli_ilce_mi(ilce, il):
        bulunan = tr_iller.ilce_bul(adres, il)
        if bulunan:
            ilce = bulunan
    # resmi il (ilce eslesmesi icin) + Surat'in bekledigi il adi (payload icin)
    resmi_il = tr_iller.resolve_il(il)
    if resmi_il:
        il = resmi_il
    surat_il = tr_iller.surat_il_adi(il)   # ornek: Afyonkarahisar -> Afyon
    return {
        "kisi": kisi,
        "adres": adres,
        "il": il,                # resmi ad (ilce dogrulama icin)
        "surat_il": surat_il,    # Surat payload icin
        "ilce": ilce,
        "telefon": _normalize_phone(sa.get("phone") or raw.get("phone")),
        "email": (raw.get("email") or raw.get("contact_email") or "").strip(),
        "ilce_gecerli": bool(il and tr_iller.gecerli_ilce_mi(ilce, il)),
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
    _s = get_settings()
    ka = kullanici_adi or _s.surat_kullanici_adi
    sf = sifre or _s.surat_sifre
    relay_url = (getattr(_s, "surat_relay_url", "") or "").strip()
    if not ka or not sf:
        return {"ok": False, "message": "Sürat kullanıcı adı/şifre tanımlı değil (.env)"}

    info = _addr_parts(order_raw)
    if not info["telefon"] or len(info["telefon"]) < 10:
        return {"ok": False, "message": f"Geçersiz telefon: '{info['telefon']}'"}
    if not info["il"] or not info["adres"]:
        return {"ok": False, "message": "Eksik adres bilgisi (il/adres)"}
    if not info.get("ilce_gecerli"):
        return {"ok": False, "message": f"İlçe belirlenemedi (il={info['il']}, ilçe='{info['ilce']}'). Adreste ilçe yok — manuel ilçe gerekli.", "ilce_eksik": True, "il": info["il"]}

    payload = {
        "KullaniciAdi": ka,
        "Sifre": sf,
        "Gonderi": {
            "KisiKurum": info["kisi"] or "Alıcı",
            "AliciAdresi": info["adres"],
            "Il": info.get("surat_il") or info["il"],
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
            "BirimDesi": "1",                # Mi: desi=1 (string — Postman formati)
            "BirimKg": "1",                  # Mi: kg=1 (string — Postman formati)
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
            "Iademi": False,                 # bool (Postman: false)
        },
    }

    surat_url = CANLI_URL if canli else TEST_URL

    def _post():
        """Tek POST; (data, http_status) doner. Hata durumunda Exception."""
        if relay_url:
            r = requests.post(
                relay_url.rstrip("/") + "/surat",
                json={"url": surat_url, "payload": payload},
                timeout=40,
            )
            r.raise_for_status()
            wrap = r.json()
            if not wrap.get("ok"):
                raise RuntimeError(f"Relay hatası: {wrap.get('error', '?')}")
            d = wrap.get("data")
            if d is None:
                raise RuntimeError(f"Relay yanıtı boş: {wrap.get('data_text', '')[:200]}")
            return d, wrap.get("status", 200)
        else:
            r = requests.post(surat_url, json=payload, timeout=30)
            return r.json(), r.status_code

    def _parse(d):
        is_err = d.get("isError", d.get("IsError", True))
        msg = str(d.get("Message", ""))
        tn = d.get("KargoTakipNo") or ""
        bc = d.get("Barcode")
        b64 = bc[0] if isinstance(bc, list) and bc else (bc if isinstance(bc, str) else None)
        ok = (not is_err) and (msg in ("013", "014", "015", "016") or bool(tn))
        return ok, tn, b64, msg

    # Surat'in bilinen bug'i: ilk cagri bazen InvalidCastException verir AMA
    # gonderi yine de olusur. Ayni OzelKargoTakipNo ile tekrar cagirinca
    # "013/016" + takip no + barkod duzgun doner. Bu yuzden 2 deneme yapariz.
    try:
        data, http_status = _post()
    except Exception as e:
        return {"ok": False, "message": f"Bağlantı hatası: {str(e)[:180]}"}

    basarili, takip_no, barkod_b64, message = _parse(data)

    # InvalidCast ya da barkodsuz/takipsiz ise: kisa bekle, ayni takip no ile tekrar dene
    needs_retry = (not basarili and "InvalidCast" in message) or (basarili and not barkod_b64)
    if needs_retry:
        import time as _t
        for _ in range(2):
            _t.sleep(1.5)
            try:
                data2, http_status = _post()
            except Exception:
                break
            ok2, tn2, b2, msg2 = _parse(data2)
            if ok2:
                basarili, takip_no, barkod_b64, message = ok2, tn2, b2, msg2
                if barkod_b64:
                    break
    return {
        "ok": bool(basarili),
        "takip_no": takip_no,
        "barkod_base64": barkod_b64,
        "message": message,
        "http_status": http_status,
        "raw_response": data if not basarili else None,  # hata ayiklama icin
    }
