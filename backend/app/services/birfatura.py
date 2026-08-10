"""BirFatura "Özel Entegrasyon" sözleşmesi — siparişleri ONLARIN beklediği
biçimde sunar.

NASIL ÇALIŞIR
─────────────
BirFatura panelinde mağaza tanımlanırken şunlar istenir:
    Mağaza Adı · Web Sitenizin Adresi · API Şifresi · Satış Kanalı Url
Verilen adrese BirFatura kendisi bağlanır ve şu 5 ucu POST'lar; API Şifresi
`token` BAŞLIĞINDA gelir, parametreler JSON gövdededir:

    /api/orderStatus/       → tanımlı sipariş durumlarımız
    /api/paymentMethods/    → tanımlı ödeme yöntemlerimiz
    /api/orders/            → {orderStatusId, startDateTime, endDateTime}
    /api/orderCargoUpdate/  → kargo takip kodunu bize yazar (opsiyonel)
    /api/invoiceLinkUpdate/ → KESİLEN FATURAYI bize yazar (no, tarih, link)

İlk üçü zorunludur. Bu modül yalnız VERİ DÖNÜŞÜMÜ yapar; HTTP ve kimlik
doğrulama routers/birfatura.py'de.

TUTAR KURALI
────────────
BirFatura "tutarları YUVARLAMADAN gönderin" der (örn. 20.0251) — kendi
hesabını kendi yapar, bizim kuruşa yuvarlamamız toplamı tutturmaz. Bu yüzden
KDV hariç değerler 6 haneye kadar ham verilir; kuruşa yuvarlama YOK.

Vitrin fiyatları KDV DAHİL olduğundan hariç değerler bölünerek bulunur.
Sepet indirimi kalemlere oransal dağıtılır (bkz. services/fatura.py) ve
BirFatura'nın istediği gibi BİRİM BAŞINA yazılır.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.services.fatura import _indirimi_dagit, _kalemler, _kdv_orani, _para

TARIH_BICIMI = "%d.%m.%Y %H:%M:%S"

# Sipariş durumları — BirFatura panelinde "hangi durumda fatura kesilsin"
# seçimi bu listeden yapılır. Fatura için doğru seçim: 1 (Ödendi).
SIPARIS_DURUMLARI = [
    (1, "Ödendi"),
    (2, "Hazırlanıyor"),
    (3, "Kargoya Verildi"),
    (4, "Teslim Edildi"),
    (5, "İptal"),
]

# Ödeme yöntemleri — sağlayıcı koduyla eşleşir
ODEME_YONTEMLERI = [
    (1, "iyzico", "Kredi Kartı (iyzico)"),
    (2, "paytr", "Kredi Kartı (PayTR)"),
    (3, "", "Diğer"),
]

TESLIM_STAGE = 9


def _tarih(dt: datetime | None) -> str | None:
    return dt.strftime(TARIH_BICIMI) if dt else None


def tarih_coz(metin: str | None) -> datetime | None:
    """BirFatura 'dd.MM.yyyy HH:mm:ss' gönderir; ISO da kabul edilir."""
    s = (metin or "").strip()
    if not s:
        return None
    for bicim in (TARIH_BICIMI, "%d.%m.%Y %H:%M", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, bicim)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _haric(dahil: Decimal, oran: Decimal) -> float:
    """KDV dahilden hariç — YUVARLAMADAN (6 hane yeter, float kaybı yok)."""
    if oran <= 0:
        return float(dahil)
    return float(round(dahil / (Decimal("1") + oran / Decimal("100")), 6))


def _odeme_tipi(saglayici: str | None) -> tuple[int, str]:
    kod = (saglayici or "").strip().lower()
    for no, anahtar, etiket in ODEME_YONTEMLERI:
        if anahtar and anahtar == kod:
            return no, etiket
    return 3, "Diğer"


def durum_no(order) -> int:
    """Siparişin BirFatura karşılığı durum numarası."""
    if order.is_iptal or order.cancelled_at:
        return 5
    if (order.current_stage or 0) >= TESLIM_STAGE:
        return 4
    if (order.kargo_info or {}).get("takip_no"):
        return 3
    if order.financial_status == "paid":
        # Ödendi ve henüz kargoya verilmedi → hem 1 hem 2 sayılır; "Ödendi"
        # daha genel olduğu için fatura seçimi orada yapılır
        return 1
    return 2


def durum_eslesir(order, istenen: int | None) -> bool:
    """orderStatusId filtresi. 1 (Ödendi) = ödenmiş ve iptal olmayan HEPSİ —
    fatura kesimi için doğru küme budur; kargolanmış sipariş de faturalanır."""
    if not istenen:
        return True
    if istenen == 1:
        return order.financial_status == "paid" and not (
            order.is_iptal or order.cancelled_at)
    return durum_no(order) == istenen


def _varyantlar(kalem_raw: dict) -> list[dict]:
    """Kalem özellikleri → BirFatura Variants (faturada satır altında görünür)."""
    cikti = []
    for ozellik in (kalem_raw.get("properties") or []):
        ad = str(ozellik.get("name") or "").strip()
        deger = str(ozellik.get("value") or "").strip()
        # Teknik alanlar faturaya girmesin
        if not ad or not deger or ad in ("Tasarım No", "Önizleme"):
            continue
        cikti.append({"Type": ad[:60], "Value": deger[:120]})
    return cikti[:5]


def siparis(order, store=None, satis_kanali: str | None = None) -> dict:
    """Bir siparişi BirFatura Orders şemasına çevir."""
    raw = order.raw or {}
    oran = _kdv_orani(store)
    oran_int = int(oran)
    musteri = raw.get("customer") or {}
    adres = raw.get("shipping_address") or {}
    fatura_bilgi = raw.get("invoice") or {}
    odeme = raw.get("payment") or {}

    kalemler = _kalemler(raw)
    indirim = _para(raw.get("total_discounts"))
    _indirimi_dagit(kalemler, indirim)
    kargo = _para(odeme.get("shipping_amount"))

    urunler_dahil = sum((k["tutar_kdv_dahil"] for k in kalemler), Decimal("0.00"))
    toplam_dahil = urunler_dahil - indirim + kargo

    ad = musteri.get("first_name") or ""
    soyad = musteri.get("last_name") or ""
    ad_soyad = f"{ad} {soyad}".strip() or (adres.get("name") or "")
    # Kurumsal fatura istendiyse fatura ADI unvandır
    fatura_adi = (fatura_bilgi.get("company") or "").strip() or ad_soyad
    telefon = adres.get("phone") or ""
    # TR: Town = İLÇE, City = İL. Bizim şemada raw.city ilçe, raw.province il.
    ilce = adres.get("city") or ""
    il = adres.get("province") or ""
    tam_adres = adres.get("address1") or ""

    odeme_no, odeme_ad = _odeme_tipi(odeme.get("provider"))
    tarih = order.created_at_platform or order.created_at

    detaylar = []
    for i, k in enumerate(kalemler):
        adet = k["adet"]
        birim_dahil = k["birim_fiyat_kdv_dahil"]
        iskonto_satir = k.get("iskonto_kdv_dahil") or Decimal("0.00")
        # BirFatura BİRİM başına iskonto ister
        iskonto_birim = (iskonto_satir / adet) if adet else Decimal("0.00")
        kalem_raw = k.get("_kaynak") or {}
        detaylar.append({
            "ProductId": i + 1,
            "ProductCode": (k["sku"] or f"URUN-{i + 1}")[:60],
            "ProductName": k["ad"][:250],
            "Variants": _varyantlar(kalem_raw),
            "ProductQuantityType": "Adet",
            "ProductQuantity": adet,
            "VatRate": oran_int,
            "ProductUnitPriceTaxIncluding": float(birim_dahil),
            "ProductUnitPriceTaxExcluding": _haric(birim_dahil, oran),
            "DiscountUnitTaxIncluding": float(round(iskonto_birim, 6)),
            "DiscountUnitTaxExcluding": _haric(iskonto_birim, oran),
        })

    kayit = {
        "OrderId": int(order.order_number) if str(order.order_number).isdigit() else 0,
        "OrderCode": str(order.order_number),
        "OrderDate": _tarih(tarih),
        "InvoiceDate": _tarih(tarih),
        "CustomerId": 0,
        "BillingName": fatura_adi[:200],
        "BillingAddress": tam_adres[:400],
        "BillingTown": ilce[:60],
        "BillingCity": il[:60],
        "BillingMobilePhone": telefon[:20],
        "BillingPhone": telefon[:20],
        "TaxOffice": (fatura_bilgi.get("tax_office") or "")[:100],
        "TaxNo": (fatura_bilgi.get("tax_no") or "")[:20],
        # TCKN toplanmıyor (KVKK veri minimizasyonu) — bireysel müşteride boş
        "SSNTCNo": "",
        "Email": raw.get("email") or musteri.get("email") or order.customer_email or "",
        "ShippingName": (adres.get("name") or ad_soyad)[:200],
        "ShippingAddress": tam_adres[:400],
        "ShippingTown": ilce[:60],
        "ShippingCity": il[:60],
        "ShippingCountry": adres.get("country") or "Türkiye",
        "ShippingZipCode": adres.get("zip") or "",
        "ShippingPhone": telefon[:20],
        "ShipCompany": (order.kargo_info or {}).get("handler_name") or "",
        "CargoCampaignCode": (order.kargo_info or {}).get("takip_no") or "",
        "SalesChannelWebSite": satis_kanali or "",
        "PaymentTypeId": odeme_no,
        "PaymentType": odeme_ad,
        "Currency": odeme.get("currency") or "TRY",
        "CurrencyRate": 1,
        "TotalPaidTaxIncluding": float(toplam_dahil),
        "TotalPaidTaxExcluding": _haric(toplam_dahil, oran),
        "ProductsTotalTaxIncluding": float(urunler_dahil),
        "ProductsTotalTaxExcluding": _haric(urunler_dahil, oran),
        "DiscountTotalTaxIncluding": float(indirim),
        "DiscountTotalTaxExcluding": _haric(indirim, oran),
        "ShippingChargeTotalTaxIncluding": float(kargo),
        "ShippingChargeTotalTaxExcluding": _haric(kargo, oran),
        "OrderDetails": detaylar,
    }
    # Fatura kesildiyse bilgisi geri gider (BirFatura tekrar kesmesin)
    f = order.fatura or {}
    if order.fatura_durum == "kesildi" and f.get("ettn"):
        kayit["ETTN"] = f["ettn"]
    return kayit


def durum_listesi() -> dict:
    return {"OrderStatus": [{"Id": i, "Value": v} for i, v in SIPARIS_DURUMLARI]}


def odeme_listesi() -> dict:
    return {"PaymentMethods": [{"Id": i, "Value": v} for i, _k, v in ODEME_YONTEMLERI]}
