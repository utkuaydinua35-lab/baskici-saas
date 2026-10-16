"""Koleksiyonlar → Meta katalog ÜRÜN SETLERİ (Shopify'ın Facebook kanalı gibi).

Ürün akışı (feed/meta.xml) Meta'ya ürünleri verir ama koleksiyonları
vermez; reklam kurarken yalnız "All products" seti görünüyordu. Burada her
aktif koleksiyon için katalogda bir ürün seti açılır/güncellenir:

    POST /{katalog_id}/product_sets   {name, filter}      → yeni set
    POST /{set_id}                    {name, filter}      → güncelle
    DELETE /{set_id}                                       → kalkan koleksiyon

Filtre: {"retailer_id": {"is_any": [slug, ...]}} — akıştaki g:id ürün slug'ı
olduğu için set üyeliği BİREBİR koleksiyonla aynıdır (metin eşleşmesi yok).
Hangi koleksiyonun hangi sete karşılık geldiği store.config["meta_urun_setleri"]
içinde tutulur: yalnız BİZİM açtığımız setler güncellenir/silinir; Meta'da
elle açılmış setlere dokunulmaz.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models import CatalogCollection, Store

logger = logging.getLogger(__name__)

GRAPH = "https://graph.facebook.com/v21.0"
SET_ON_EK = ""          # set adı = koleksiyon adı (reklam ekranında aynen görünür)


class KatalogHatasi(Exception):
    pass


def _istek(yontem: str, yol: str, token: str, veri: dict | None = None) -> dict:
    """Graph API çağrısı. Testte bu fonksiyon değiştirilir (Meta'ya gidilmez)."""
    import httpx
    r = httpx.request(yontem, f"{GRAPH}/{yol}", params={"access_token": token},
                      data=veri, timeout=20)
    try:
        govde = r.json()
    except ValueError:
        govde = {}
    if r.status_code >= 400 or "error" in govde:
        hata = (govde.get("error") or {})
        raise KatalogHatasi(f"{hata.get('code', r.status_code)}: {hata.get('message', 'bilinmeyen hata')}"[:300])
    return govde


def ayarli_mi(store: Store) -> bool:
    c = store.config or {}
    return bool((c.get("meta_catalog_id") or "").strip() and (c.get("meta_catalog_token") or "").strip())


def esitle(db: Session, store: Store) -> dict:
    """Mağazanın aktif koleksiyonlarını Meta ürün setleriyle eşitle."""
    cfg = dict(store.config or {})
    katalog = (cfg.get("meta_catalog_id") or "").strip()
    token = (cfg.get("meta_catalog_token") or "").strip()
    if not katalog or not token:
        raise KatalogHatasi("Meta katalog kimliği ve anahtarı girilmemiş")

    eslesme: dict[str, str] = dict(cfg.get("meta_urun_setleri") or {})
    sonuc = {"acilan": 0, "guncellenen": 0, "silinen": 0, "atlanan": 0, "hatalar": []}
    gorulen: set[str] = set()

    koleksiyonlar = db.scalars(select(CatalogCollection).where(
        CatalogCollection.store_id == store.id, CatalogCollection.is_active.is_(True),
    ).order_by(CatalogCollection.position)).all()
    for kol in koleksiyonlar:
        # Akışla AYNI ürünler: yalnız yayındakiler (taslak/özel ürün akışta yok)
        sluglar = sorted(p.slug for p in kol.products if p.status == "active")
        if not sluglar:
            sonuc["atlanan"] += 1
            continue
        anahtar = str(kol.id)
        gorulen.add(anahtar)
        veri = {"name": f"{SET_ON_EK}{kol.title}"[:100],
                "filter": json.dumps({"retailer_id": {"is_any": sluglar}})}
        set_id = eslesme.get(anahtar)
        try:
            if set_id:
                try:
                    _istek("POST", set_id, token, veri)
                    sonuc["guncellenen"] += 1
                    continue
                except KatalogHatasi as e:
                    # Set Meta'da elle silinmiş olabilir → yeniden aç
                    if not str(e).startswith("100"):
                        raise
            yeni = _istek("POST", f"{katalog}/product_sets", token, veri)
            eslesme[anahtar] = str(yeni["id"])
            sonuc["acilan"] += 1
        except KatalogHatasi as e:
            sonuc["hatalar"].append(f"{kol.title}: {e}")

    # Kaldırılan/pasif/boş koleksiyonların setleri (yalnız bizim açtıklarımız)
    for anahtar in [k for k in eslesme if k not in gorulen]:
        try:
            _istek("DELETE", eslesme[anahtar], token)
            sonuc["silinen"] += 1
            eslesme.pop(anahtar)
        except KatalogHatasi as e:
            if str(e).startswith("100"):     # zaten yok
                eslesme.pop(anahtar)
            else:
                sonuc["hatalar"].append(f"silinemedi ({anahtar[:8]}): {e}")

    cfg["meta_urun_setleri"] = eslesme
    cfg["meta_urun_setleri_son"] = {
        "zaman": datetime.now(timezone.utc).isoformat(),
        **{k: v for k, v in sonuc.items() if k != "hatalar"},
        "hata_sayisi": len(sonuc["hatalar"]),
    }
    store.config = cfg
    flag_modified(store, "config")
    db.commit()
    return sonuc


def tum_magazalari_esitle(db: Session) -> dict:
    """Gece işi: katalog ayarı olan her vitrin mağazası."""
    ozet = {}
    for st in db.scalars(select(Store).where(Store.platform == "storefront")).all():
        if not ayarli_mi(st):
            continue
        try:
            ozet[st.slug] = esitle(db, st)
        except Exception as e:  # noqa: BLE001 — bir mağaza diğerini durdurmasın
            db.rollback()
            ozet[st.slug] = {"hata": str(e)[:200]}
            logger.warning("[meta-katalog] %s: %s", st.slug, e)
    return ozet
