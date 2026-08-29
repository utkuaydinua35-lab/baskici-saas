"""
Sürat Kargo entegrasyonu — OrtakBarkodOlustur

Gönderi oluşturur, takip no + barkod (base64 PDF) döndürür.
Canlı: https://api01.suratkargo.com.tr/api/OrtakBarkodOlustur
Test : https://api02.suratkargo.com.tr/api/OrtakBarkodOlustur
"""
from __future__ import annotations

import logging
import re

import requests

from app.config import get_settings
from app.services import tr_iller

logger = logging.getLogger("surat")

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
    # resmi il (ilce eslesmesi icin)
    resmi_il = tr_iller.resolve_il(il)
    # İl çözülemediyse (örn province boş, city='Merkez') posta kodundan (TR plaka) bul.
    # Bu durumda eldeki "il" değeri aslında ilçedir (Merkez/Şahinbey gibi) — ilçeye taşı.
    if not resmi_il:
        zip_il = tr_iller.il_from_zip(sa.get("zip"))
        if zip_il:
            if il and not (ilce or "").strip():
                ilce = il
            resmi_il = zip_il
    # Hâlâ yoksa: SERBEST ADRES METNİNDEN çıkar. Elle/bayii/Instagram siparişlerinde
    # province/city boş gelip her şey adres satırına yazılabiliyor
    # ("... No:8 Daire:7 YALOVA/MERKEZ Koza Mesken Apt.") — eskiden bu durumda
    # il hiç çözülemiyor ve kargo oluşturulamıyordu.
    if not resmi_il:
        _metin = " ".join(x for x in [
            adres, (sa.get("city") or ""), (sa.get("province") or ""),
            (sa.get("address2") or ""), (sa.get("company") or ""),
        ] if x)
        resmi_il = tr_iller.il_bul(_metin)
    # Son çare: elde il sanılan değer aslında BENZERSİZ bir ilçe adıysa
    # (province boş, city='Kadıköy') ilini oradan türet.
    if not resmi_il:
        for _aday in (sa.get("city"), sa.get("province"), il):
            _t = tr_iller.il_from_ilce(_aday)
            if _t:
                if not (ilce or "").strip():
                    ilce = _aday
                resmi_il = _t
                break
    if resmi_il:
        il = resmi_il
    # ilce gecerli mi? degilse GENIS metinden cikarmayi dene (cozulen il ile).
    # Ilce alani cok kelimeli ('Ankara Etimesgut'), il/ilce swap edilmis
    # (province=Etimesgut, city=Ankara) ya da ilce sadece adres metninde olabilir.
    # Bu yuzden ilce + ham city + ham province + adres birlesik taranir.
    if il and not tr_iller.gecerli_ilce_mi(ilce, il):
        _search = " ".join(x for x in [
            (ilce or ""), (sa.get("city") or ""), (sa.get("province") or ""), adres,
        ] if x)
        bulunan = tr_iller.ilce_bul(_search, il)
        if bulunan:
            ilce = bulunan
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


def is_configured() -> bool:
    _s = get_settings()
    return bool(_s.surat_kullanici_adi and _s.surat_sifre)


def create_shipment(
    order_raw: dict,
    *,
    ozel_kargo_takip_no: str,
    canli: bool = True,
    kullanici_adi: str | None = None,
    sifre: str | None = None,
    il_override: str | None = None,
    ilce_override: str | None = None,
) -> dict:
    """
    Sürat'a gönderi oluşturur.
    Returns: {ok, takip_no, barkod_base64, message, raw_response}
    """
    _s = get_settings()
    ka = kullanici_adi or _s.surat_kullanici_adi
    sf = sifre or _s.surat_sifre
    if not ka or not sf:
        return {"ok": False, "message": "Sürat kullanıcı adı/şifre tanımlı değil (.env)"}

    info = _addr_parts(order_raw)
    # Adres çözülemeyen siparişlerde panelden elle seçilen il/ilçe
    # (Basit Kargo akışıyla aynı davranış).
    if il_override and ilce_override:
        info["il"] = tr_iller.resolve_il(il_override) or il_override
        info["ilce"] = ilce_override
        info["surat_il"] = tr_iller.surat_il_adi(info["il"])
        info["ilce_gecerli"] = True
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
        r = requests.post(surat_url, json=payload, timeout=30)
        return r.json(), r.status_code

    def _tekil(v):
        """Sürat bazı alanları LİSTE olarak veriyor (Barcode/BarcodeNo)."""
        if isinstance(v, list):
            return v[0] if v else None
        return v if isinstance(v, str) and v.strip() else None

    def _parse(d):
        is_err = d.get("isError", d.get("IsError", True))
        msg = str(d.get("Message", ""))
        tn = d.get("KargoTakipNo") or ""
        b64 = _tekil(d.get("Barcode"))
        bno = _tekil(d.get("BarcodeNo"))
        ok = (not is_err) and (msg in ("013", "014", "015", "016") or bool(tn))
        return ok, tn, b64, bno, msg

    # Surat'in bilinen bug'i: ilk cagri bazen InvalidCastException verir AMA
    # gonderi yine de olusur. Ayni OzelKargoTakipNo ile tekrar cagirinca
    # "013/016" + takip no + barkod duzgun doner. Bu yuzden 2 deneme yapariz.
    try:
        data, http_status = _post()
    except Exception as e:
        return {"ok": False, "message": f"Bağlantı hatası: {str(e)[:180]}"}

    basarili, takip_no, barkod_b64, barkod_no, message = _parse(data)

    # Yalnizca InvalidCastException icin yeniden dene (Surat'in bilinen hatasi).
    #
    # Eskiden "basarili ama barkod yok" da yeniden deneniyordu. 2026-08-29 canli
    # logu gosterdi ki bu hesapta Barcode/BarcodeNo HER ZAMAN bos donuyor; kosul
    # her gonderide 3 cagri yapiyor, ~3 sn gecikme ekliyor ve Surat
    # OzelKargoTakipNo'da idempotent degilse MUKERRER GONDERI acabiliyordu.
    # Barkod gelmemesi normal kabul edilir; etiket yedegi devreye girer.
    needs_retry = (not basarili) and "InvalidCast" in message
    if needs_retry:
        import time as _t
        for _ in range(2):
            _t.sleep(1.5)
            try:
                data2, http_status = _post()
            except Exception:
                break
            ok2, tn2, b2, bn2, msg2 = _parse(data2)
            if ok2:
                basarili, takip_no, barkod_b64, message = ok2, tn2, b2, msg2
                barkod_no = bn2 or barkod_no
                if barkod_b64:
                    break
    # Yanitin KUNYESINI her zaman logla. Basarili cagrilarda yanit atiliyordu;
    # Surat takip no verip barkod VERMEYINCE elimizde hicbir iz kalmiyordu.
    # Kimlik bilgisi yanitta yer almaz, gizlenecek bir sey yok.
    try:
        logger.info(
            "[surat] ok=%s msg=%s takip=%s barkod_pdf=%s barkod_no=%s Value=%s alanlar=%s",
            bool(basarili), message, takip_no or "-",
            f"{len(barkod_b64)} krk" if barkod_b64 else "YOK",
            barkod_no or "YOK",
            str(data.get("Value"))[:120] if isinstance(data, dict) else "-",
            ",".join(sorted(data.keys())) if isinstance(data, dict) else type(data).__name__,
        )
    except Exception:  # noqa: BLE001
        pass
    return {
        "ok": bool(basarili),
        "takip_no": takip_no,
        "barkod_base64": barkod_b64,
        "barkod_no": barkod_no,
        "message": message,
        "http_status": http_status,
        "raw_response": data if not basarili else None,  # hata ayiklama icin
    }
