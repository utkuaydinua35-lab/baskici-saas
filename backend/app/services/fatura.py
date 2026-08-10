"""Siparişten FATURA VERİSİ üretir — e-fatura entegratörünün okuyacağı biçim.

NEDEN BU MODÜL VAR
──────────────────
Faturayı GİB'e ileten taraf entegratördür (Birfatura, Nilvera, İzibiz…):
mali mühürle imzalama, UBL-TR zarfı, e-Arşiv raporu onların işi. Bize düşen,
siparişi FATURAYA HAZIR ve tutarları tutan bir veri hâline getirmek. Bu modül
tek doğruluk kaynağıdır: entegrasyon API'si de, ileride eklenecek herhangi bir
"doğrudan gönder" adaptörü de aynı çıktıyı kullanır.

TUTAR KURALLARI (Türkiye)
─────────────────────────
• Vitrin fiyatları KDV DAHİL gösterilir. Faturada matrah (KDV hariç) ve KDV
  ayrı satırlar hâlinde ister; ayrıştırma: matrah = tutar / (1 + oran).
• İNDİRİM satırlara ORANSAL dağıtılır. Faturada "sepete 50 TL indirim" diye
  bir satır olmaz; her kalemin kendi iskontosu olur. Dağıtımdaki kuruş artığı
  en büyük satıra eklenir, böylece kalemler toplamı sipariş tutarına BİREBİR
  eşitlenir — entegratör tutar tutmazsa faturayı reddeder.
• KARGO ücreti ayrı bir kalem olarak gider (KDV'si aynı orandan).
• Tutarı 0 olan kalemler (couple setin 2. kılıfı gibi) faturaya GİRMEZ; onlar
  üretim kalemidir, bedeli ilk satırdadır.

ALICI TİPİ
──────────
VKN varsa "tuzel" (şirket), yoksa "gercek" (bireysel). e-Fatura mükellefi olup
olmadığını GİB kayıtlı kullanıcı listesinden ENTEGRATÖR sorgular — bizde o
liste yok, bu yüzden yalnız ipucu veririz.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

KURUS = Decimal("0.01")
VARSAYILAN_KDV = Decimal("20")


def _para(v) -> Decimal:
    try:
        return Decimal(str(v or 0)).quantize(KURUS, rounding=ROUND_HALF_UP)
    except Exception:  # noqa: BLE001 — bozuk veri faturayı düşürmesin
        return Decimal("0.00")


def _kdv_orani(store) -> Decimal:
    try:
        ham = (store.config or {}).get("tax_rate") if store else None
        oran = Decimal(str(ham)) if ham not in (None, "") else VARSAYILAN_KDV
        return oran if oran >= 0 else VARSAYILAN_KDV
    except Exception:  # noqa: BLE001
        return VARSAYILAN_KDV


def _matrah_kdv(dahil: Decimal, oran: Decimal) -> tuple[Decimal, Decimal]:
    """KDV DAHİL tutardan (matrah, kdv) — ikisinin toplamı dahil tutara eşit."""
    if oran <= 0:
        return dahil, Decimal("0.00")
    matrah = (dahil / (Decimal("1") + oran / Decimal("100"))).quantize(
        KURUS, rounding=ROUND_HALF_UP)
    return matrah, dahil - matrah


def _kalemler(raw: dict) -> list[dict]:
    """Faturaya girecek satırlar: bedeli olanlar (0 TL üretim satırları hariç)."""
    cikti = []
    for k in (raw.get("line_items") or []):
        adet = int(k.get("quantity") or 1)
        birim = _para(k.get("price"))
        if adet <= 0 or birim <= 0:
            continue
        cikti.append({
            "ad": " — ".join(x for x in (k.get("title"), k.get("variant_title")) if x)[:250],
            "sku": k.get("sku") or None,
            "adet": adet,
            "birim_fiyat_kdv_dahil": birim,
            "tutar_kdv_dahil": _para(birim * adet),
            # Kaynak satır — BirFatura eşlemesi varyantları buradan okur
            "_kaynak": k,
        })
    return cikti


def _indirimi_dagit(kalemler: list[dict], indirim: Decimal) -> None:
    """İndirimi kalemlere tutarları oranında dağıt; artığı en büyük satıra ver."""
    if indirim <= 0 or not kalemler:
        return
    toplam = sum(k["tutar_kdv_dahil"] for k in kalemler)
    if toplam <= 0:
        return
    indirim = min(indirim, toplam)          # indirim tutarı aşamaz
    dagitilan = Decimal("0.00")
    for k in kalemler:
        pay = (indirim * k["tutar_kdv_dahil"] / toplam).quantize(
            KURUS, rounding=ROUND_HALF_UP)
        k["iskonto_kdv_dahil"] = pay
        dagitilan += pay
    artik = indirim - dagitilan
    if artik:
        en_buyuk = max(kalemler, key=lambda k: k["tutar_kdv_dahil"])
        en_buyuk["iskonto_kdv_dahil"] += artik


def fatura_verisi(order, store=None) -> dict:
    """Sipariş → fatura kesmeye hazır veri. Tutarlar string (float yuvarlama yok)."""
    raw = order.raw or {}
    musteri = raw.get("customer") or {}
    adres = raw.get("shipping_address") or {}
    fatura_bilgi = raw.get("invoice") or {}
    oran = _kdv_orani(store)

    kalemler = _kalemler(raw)
    kargo = _para(((raw.get("payment") or {}).get("shipping_amount")))
    indirim = _para(raw.get("total_discounts"))
    _indirimi_dagit(kalemler, indirim)

    satirlar = []
    ara_matrah = ara_kdv = Decimal("0.00")
    for k in kalemler:
        iskonto = k.get("iskonto_kdv_dahil") or Decimal("0.00")
        net_dahil = k["tutar_kdv_dahil"] - iskonto
        matrah, kdv = _matrah_kdv(net_dahil, oran)
        ara_matrah += matrah
        ara_kdv += kdv
        birim_matrah, _ = _matrah_kdv(k["birim_fiyat_kdv_dahil"], oran)
        satirlar.append({
            "ad": k["ad"],
            "sku": k["sku"],
            "adet": k["adet"],
            "birim": "Adet",
            "birim_fiyat": str(birim_matrah),          # KDV hariç
            "iskonto": str(_matrah_kdv(iskonto, oran)[0]) if iskonto else "0.00",
            "matrah": str(matrah),
            "kdv_orani": str(oran),
            "kdv_tutari": str(kdv),
            "toplam": str(net_dahil),                  # KDV dahil satır toplamı
        })

    if kargo > 0:
        matrah, kdv = _matrah_kdv(kargo, oran)
        ara_matrah += matrah
        ara_kdv += kdv
        satirlar.append({
            "ad": "Kargo bedeli", "sku": None, "adet": 1, "birim": "Adet",
            "birim_fiyat": str(matrah), "iskonto": "0.00", "matrah": str(matrah),
            "kdv_orani": str(oran), "kdv_tutari": str(kdv), "toplam": str(kargo),
        })

    genel = ara_matrah + ara_kdv
    vkn = (fatura_bilgi.get("tax_no") or "").strip()
    unvan = (fatura_bilgi.get("company") or "").strip()
    ad_soyad = " ".join(x for x in (musteri.get("first_name"), musteri.get("last_name")) if x)

    return {
        "siparis_no": order.order_number,
        "siparis_tarihi": (order.created_at_platform or order.created_at).isoformat()
        if (order.created_at_platform or order.created_at) else None,
        "para_birimi": ((raw.get("payment") or {}).get("currency") or "TRY"),
        "odeme": {
            "yontem": "Kredi Kartı",
            "saglayici": (raw.get("payment") or {}).get("provider"),
            "referans": (raw.get("payment") or {}).get("provider_ref"),
        },
        "alici": {
            # VKN varsa tüzel kişi (şirket) — faturası e-Fatura kanalına
            # düşebilir; kontrolü entegratör GİB listesinden yapar
            "tip": "tuzel" if vkn else "gercek",
            "unvan": unvan or ad_soyad or (adres.get("name") or ""),
            "ad": musteri.get("first_name") or "",
            "soyad": musteri.get("last_name") or "",
            "vkn": vkn or None,
            "vergi_dairesi": (fatura_bilgi.get("tax_office") or "").strip() or None,
            "eposta": raw.get("email") or musteri.get("email") or order.customer_email,
            "telefon": adres.get("phone") or None,
        },
        "adres": {
            "adres": adres.get("address1") or "",
            "ilce": adres.get("city") or "",       # Shopify şemasında city=ilçe
            "il": adres.get("province") or "",
            "posta_kodu": adres.get("zip") or None,
            "ulke": adres.get("country") or "Türkiye",
        },
        "kalemler": satirlar,
        "toplamlar": {
            "matrah": str(ara_matrah),
            "toplam_iskonto": str(indirim),
            "kdv_orani": str(oran),
            "kdv_tutari": str(ara_kdv),
            "genel_toplam": str(genel),
        },
        "not": raw.get("note") or None,
        "fatura_durum": order.fatura_durum,
        "fatura": order.fatura or None,
    }
