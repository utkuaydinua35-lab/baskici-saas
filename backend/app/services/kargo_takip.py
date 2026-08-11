"""Kargo firmasi + takip no -> firmanin kendi takip sayfasinin DOGRUDAN linki.

Kendi kargo anlasmasiyla ve Basit Kargo ile calisirken takip URL'i hicbir yerden
gelmiyordu (yalnizca Shopify ve Birfatura gonderiyor). Panelde takip numarasi
yaziyor ama tiklanabilir degildi; numarayi kopyalayip firmanin sitesinde elle
aramak gerekiyordu.

SABLONLARI DEGISTIRMEK: asagidaki tablo tek kaynak. Bir firma linki yanlis
sayfaya goturuyorsa yalnizca o satiri duzelt — baska hicbir yeri degistirmeye
gerek yok.
"""
from __future__ import annotations

from urllib.parse import quote

# Anahtar: firma adinda ARANAN kelime (normalize edilmis, kucuk harf).
# Deger: {takip_no} yerine numaranin konacagi sablon.
#
# Kaynak notu: Sablonlar firmalarin herkese acik takip sayfalarindan. Turk kargo
# siteleri bot isteklerini engelledigi icin otomatik dogrulanamiyor — bir firma
# icin link yanlis sayfaya duserse ilgili satiri duzeltmek yeterli.
SABLONLAR: dict[str, str] = {
    "surat": "https://www.suratkargo.com.tr/KargoTakip/?kargotakipno={takip_no}",
    "yurtici": "https://www.yurticikargo.com/tr/online-servisler/gonderi-sorgula?code={takip_no}",
    "aras": "https://kargotakip.araskargo.com.tr/mainpage.aspx?code={takip_no}",
    "mng": "https://kargotakip.mngkargo.com.tr/?takipNo={takip_no}",
    "ptt": "https://gonderitakip.ptt.gov.tr/Track/Verify?q={takip_no}",
    "ups": "https://www.ups.com/track?loc=tr_TR&tracknum={takip_no}",
    "hepsijet": "https://www.hepsijet.com/gonderi-takibi?trackingId={takip_no}",
    "sendeo": "https://sendeo.com.tr/kargo-takip?kod={takip_no}",
}

# Basit Kargo'nun kendi takip sayfasi — gercek firma cozulemedigi zaman.
BASIT_KARGO_SABLON = "https://basitkargo.com/takip/{takip_no}"


def _normalize(s: str | None) -> str:
    """TR karakterleri sadelestir, kucuk harfe indir."""
    out = (s or "").strip().lower()
    for a, b in (("ı", "i"), ("İ", "i"), ("ş", "s"), ("ç", "c"),
                 ("ö", "o"), ("ü", "u"), ("ğ", "g")):
        out = out.replace(a, b)
    return out


def takip_url(kargo_firma: str | None, takip_no: str | None) -> str | None:
    """Firmanin takip sayfasina, numara doldurulmus DOGRUDAN link.

    Firma taninmazsa None doner — tahmini bir URL uretmek, calismayan bir
    baglanti gostermekten daha kotu.
    """
    no = (takip_no or "").strip()
    if not no:
        return None
    ad = _normalize(kargo_firma)
    if not ad:
        return None

    # "Basit Kargo (Ekonomik)" gibi agregator adlarinda gercek firma belli degil;
    # agregatorun kendi takip sayfasina goturulur.
    if "basit" in ad:
        return BASIT_KARGO_SABLON.format(takip_no=quote(no, safe=""))

    for anahtar, sablon in SABLONLAR.items():
        if anahtar in ad:
            return sablon.format(takip_no=quote(no, safe=""))
    return None


def coz(kargo_firma: str | None, takip_no: str | None,
        mevcut_url: str | None = None) -> str | None:
    """Kayitli URL varsa ONU kullan, yoksa firmadan uret.

    Shopify ve Birfatura gercek takip URL'ini gonderiyor; o her zaman
    sablondan daha guvenilir.
    """
    kayitli = (mevcut_url or "").strip()
    if kayitli:
        return kayitli
    return takip_url(kargo_firma, takip_no)
