"""Hepsiburada kanalından gelen bayi siparişleri — tek kaynak.

Hepsiburada'da gönderi Hepsiburada'nın sisteminde açılır; satıcıya bir KARGO
ENTEGRASYON KODU verilir. Kargo şubesi paketi bu kodla tanır. Bu yüzden:

  • Bayiden kod ZORUNLU istenir (yoksa paket kargoya teslim edilemez).
  • Paketlemede bizim kargo firmamızda yeni gönderi AÇILMAZ — açılsaydı paket
    Hepsiburada'nın gönderisiyle eşleşmez, müşteri takip göremezdi.
  • Etiket özeldir: maskeli alıcı adı + kargo firması + kodun barkodu.

Adres Hepsiburada'da durur; bizden yalnız alıcı adı istenir (Trendyol gibi).
"""
from __future__ import annotations

import re

from app.services import barcode128

KANAL = "hepsiburada"

# Sıra = formdaki sıra. İlki varsayılan (Sürat).
KARGO_FIRMALARI: dict[str, str] = {
    "surat": "Sürat Kargo",
    "hepsijet": "HepsiJET",
    "aras": "Aras Kargo",
    "yurtici": "Yurtiçi Kargo",
    "mng": "MNG Kargo",
    "ptt": "PTT Kargo",
}
VARSAYILAN_FIRMA = "surat"

KOD_EN_KISA = 6
KOD_EN_UZUN = 40
_KOD_DESENI = re.compile(r"^[A-Za-z0-9-]+$")


class KodHatasi(ValueError):
    pass


def kod_temizle(kod: str | None) -> str:
    """Kodu barkoda basılacak biçime getir.

    ⚠ İÇ BOŞLUKLAR atılır: "4010 5913 4531" diye kopyalanan kod boşluklu
    basılırsa rakam-yalnız sayılmaz, Code128-B'ye düşer (çubuklar incelir) ve
    okuyucu boşluklu metin verir — kargo sistemi bunu tanımaz.
    """
    return "".join(str(kod or "").split())


def kod_dogrula(kod: str | None) -> str:
    """Temizlenmiş geçerli kodu döndür; geçersizse KodHatasi."""
    k = kod_temizle(kod)
    if not k:
        raise KodHatasi("Hepsiburada siparişinde kargo entegrasyon kodu zorunlu")
    if not KOD_EN_KISA <= len(k) <= KOD_EN_UZUN:
        raise KodHatasi(f"Kargo entegrasyon kodu {KOD_EN_KISA}-{KOD_EN_UZUN} karakter olmalı")
    if not _KOD_DESENI.match(k) or barcode128.temizle(k) != k:
        raise KodHatasi("Kargo entegrasyon kodunda yalnız harf, rakam ve tire olabilir")
    return k


def firma_dogrula(firma: str | None) -> str:
    f = (firma or "").strip().lower() or VARSAYILAN_FIRMA
    if f not in KARGO_FIRMALARI:
        raise KodHatasi(f"Geçersiz kargo firması. Seçenekler: {', '.join(KARGO_FIRMALARI)}")
    return f


def firma_adi(firma: str | None) -> str:
    return KARGO_FIRMALARI.get((firma or "").lower(), KARGO_FIRMALARI[VARSAYILAN_FIRMA])


def _tr_buyuk(s: str) -> str:
    return s.replace("i", "İ").replace("ı", "I").upper()


def maskele(ad: str | None) -> str:
    """Her sözcüğün ilk 3 harfi açık, kalanı yıldız: "Ayşe Yılmaz" → "AYŞ* YIL***".

    3 harf ve altındaki sözcük olduğu gibi kalır (maskelenecek harf yok).
    Pakette alıcının tam adı görünmez — pazaryeri etiketlerindeki uygulama.
    """
    sozcukler = (ad or "").split()
    if not sozcukler:
        return "***"
    return " ".join(_tr_buyuk(s[:3]) + "*" * max(0, len(s) - 3) for s in sozcukler)


def bilgi(order) -> dict | None:
    """Sipariş Hepsiburada kanalındansa etiket/gönderi bilgisi, değilse None."""
    raw = getattr(order, "raw", None) or {}
    if raw.get("kanal") != KANAL:
        return None
    return {
        "kod": kod_temizle(raw.get("kargo_entegrasyon_kodu")),
        "firma": raw.get("kargo_firma") or VARSAYILAN_FIRMA,
        "firma_adi": firma_adi(raw.get("kargo_firma")),
        "alici": maskele((raw.get("shipping_address") or {}).get("name")
                         or getattr(order, "customer_name", "")),
    }
