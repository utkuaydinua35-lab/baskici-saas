"""Müşterinin değişiklik bağlantısından ÜRÜN (tasarım) değiştirmesi.

ÖNCE: ürün değişikliği yalnız bildirim + geçmiş notuydu ("tasarımı elle
bağlayın"). Kalem ESKİ tasarımıyla kalıyor, kalıptan çekildiği için bir sonraki
planda eski tasarımla YENİDEN kalıba giriyordu. Sipariş detayında da hiçbir
iz yoktu (#11701 — kişiye özel fotoğraflı kılıf; müşteri iki kez başka
tasarım seçti, kalem hâlâ fotoğraflı tasarıma bağlıydı).

ŞİMDİ:
  • Tasarım KESİN bulunursa otomatik bağlanır (Shopify mağazasında
    Design.product_id = Shopify ürün kimliği; müşterinin seçtiği katalog ürünü
    de Shopify ürünü — kimlikler aynı uzayda).
  • Bulunamazsa (tasarım yok / birden fazla aday / vitrin kataloğu) kalem
    "tasarım bekliyor" olur: KALIBA GİRMEZ, sipariş detayında uyarı çıkar;
    operatör tasarım kodu bağlar, tekrar dener ya da yok sayar.

Kayıt kalemin `urun_degisikligi` sütununda (raw'da değil — Shopify senkronu
raw/title/product_id'yi her seferinde ezer).

Tahmin YOK: yanlış tasarımı bağlamak çöp kılıf demek; emin olunmayan her
durumda bekletilir.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Design, LineItem, Store

BEKLIYOR, UYGULANDI, YOKSAYILDI = "bekliyor", "uygulandi", "yoksayildi"


def bekliyor_mu(li: LineItem) -> bool:
    return (getattr(li, "urun_degisikligi", None) or {}).get("durum") == BEKLIYOR


def uygulandi_mi(li: LineItem) -> bool:
    return (getattr(li, "urun_degisikligi", None) or {}).get("durum") == UYGULANDI


def _simdi() -> str:
    return datetime.now(UTC).isoformat()


def _kalem_varyasyonu(li: LineItem) -> str | None:
    from app.services import mold_planner, placement_rules as pr
    v, _ = mold_planner.resolve_line_variation_detail(
        li, li.assigned_design if li.assigned_design_id else None)
    return pr.normalize_variation(v) if v else None


def tasarim_bul(db: Session, store: Store | None, urun_id: str, li: LineItem) -> tuple[Design | None, str | None]:
    """(tasarım, None) ya da (None, neden). Emin olunmayan her durumda tasarım yok."""
    if store is None or (store.platform or "").lower() != "shopify":
        return None, "Bu mağazanın kataloğu tasarımlara otomatik bağlanamıyor"
    adaylar = [d for d in db.scalars(select(Design).where(
        Design.store_id == store.id, Design.product_id == str(urun_id),
    )).all() if not getattr(d, "baski_dosyasi_yok", False)
        and getattr(d, "dosya_silindi_at", None) is None]
    if not adaylar:
        return None, "Seçilen ürünün baskı tasarımı sistemde yok"
    if len(adaylar) == 1:
        return adaylar[0], None
    # Varyantlı ürün: varyanta özel olmayan (genel) tasarım tekse o
    genel = [d for d in adaylar if not d.variant_id]
    if len(genel) == 1:
        return genel[0], None
    # Birden fazla: kalemin mevcut kılıf türüyle (şeffaf/parlak/...) eşleşen TEK aday
    from app.services import placement_rules as pr
    var = _kalem_varyasyonu(li)
    if var:
        eslesen = [d for d in (genel or adaylar)
                   if d.kalip_tipi and pr.normalize_variation(d.kalip_tipi) == var]
        if len(eslesen) == 1:
            return eslesen[0], None
    return None, f"Seçilen ürünün {len(adaylar)} tasarımı var — hangisi olduğu belirsiz"


def _onceki(li: LineItem) -> dict:
    return {
        "title": li.title, "product_id": li.product_id,
        "assigned_design_id": str(li.assigned_design_id) if li.assigned_design_id else None,
        "kilif_varyasyon": li.kilif_varyasyon,
    }


def tasarimi_bagla(li: LineItem, design: Design, kim: str) -> None:
    """Tasarımı kaleme bağla. Model aynı kalır; kılıf türü yeni tasarımdan gelir.

    Yalnız uygulamaya ait alanlar yazılır (senkron ezmez): assigned_design_id,
    kilif_varyasyon, device_model_override, product_image_url, urun_degisikligi.
    """
    from app.services import mold_planner, placement_rules as pr
    kayit = dict(li.urun_degisikligi or {})
    kayit.setdefault("onceki", _onceki(li))
    # Model property/variant'tan geliyorsa sabitle: ürün değişince eski ürünün
    # variant_title'ı anlamını yitirir.
    if not (li.device_model_override or "").strip():
        m = mold_planner.extract_phone_model(li)
        if m:
            li.device_model_override = m[:100]
    li.assigned_design_id = design.id
    li.kilif_varyasyon = pr.normalize_variation(design.kalip_tipi) if design.kalip_tipi else None
    if design.product_image_url:
        li.product_image_url = design.product_image_url
    li.is_kaliba_eklendi = False
    li.is_hazir = False
    kayit.update(durum=UYGULANDI, tasarim_id=str(design.id), tasarim_kodu=design.code,
                 karar_at=_simdi(), karar_veren=kim, sebep=None)
    li.urun_degisikligi = kayit


def kaydet(db: Session, li: LineItem, store: Store | None, *, urun_id: str, baslik: str,
           gorsel: str | None, kim: str = "Müşteri") -> dict:
    """Müşterinin seçimini kaydet; tasarım kesinse bağla, değilse beklet."""
    kayit = {
        "durum": BEKLIYOR, "urun_id": str(urun_id), "baslik": baslik, "gorsel": gorsel,
        "at": _simdi(), "kaynak": kim,
        # Önceki değişiklik uygulandıysa "önceki" ilk (orijinal) hal kalsın
        "onceki": (li.urun_degisikligi or {}).get("onceki") or _onceki(li),
    }
    li.urun_degisikligi = kayit
    design, neden = tasarim_bul(db, store, urun_id, li)
    if design is not None:
        tasarimi_bagla(li, design, kim=f"otomatik ({kim})")
    else:
        kayit = dict(li.urun_degisikligi)
        kayit["sebep"] = neden
        li.urun_degisikligi = kayit
    return li.urun_degisikligi


def yoksay(li: LineItem, kim: str) -> None:
    kayit = dict(li.urun_degisikligi or {})
    kayit.update(durum=YOKSAYILDI, karar_at=_simdi(), karar_veren=kim)
    li.urun_degisikligi = kayit
