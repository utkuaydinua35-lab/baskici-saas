"""Kısıtlı hazır şablon — müşteri yalnız tanımlı alanları doldurur.

Örnekler:
- FORMA: zemin sabit, müşteri numara + isim yazar, bayrak/logo açıp kapatır.
- FOTOĞRAF ÇERÇEVESİ: müşteri tek görsel yükler, çerçeveye otomatik oturur.
- SPOTIFY ARAYÜZÜ: müşteri albüm kapağını yükler, şarkı adını ve süreleri
  yazar; ilerleme çubuğunun noktası geçen/toplam süreye göre kendi kayar.

Bu modül alan DEĞERLERİNDEN çizim katmanlarını üretir. Konum, font, renk, punto
ve şablon dosyaları HEP ŞABLONDAN gelir; müşteriden sadece metin, aç/kapa ve
yüklediği görselin kimliği alınır. Katmanlar sunucuda burada üretildiği için
müşteri gövdeyi değiştirse bile baskıya şablonun dışına çıkan bir şey giremez.

İstemcideki eşi (canlı önizleme için aynı kuralları uygular):
storefront/components/studio/kisitli.ts → kisitliKatmanlar()
"""
from __future__ import annotations

MAX_METIN = 40


def _sayi(v, varsayilan: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return varsayilan


def saniye_coz(metin: str | None) -> float | None:
    """"3:07" / "03:07" / "187" → saniye. Çözemezse None."""
    s = str(metin or "").strip()
    if not s:
        return None
    try:
        if ":" in s:
            parcalar = [int(p) for p in s.split(":")]
            toplam = 0
            for p in parcalar:
                toplam = toplam * 60 + p
            return float(toplam)
        return float(s)
    except (TypeError, ValueError):
        return None


def kapla_crop(alan: dict, kaynak_w: int, kaynak_h: int) -> dict | None:
    """Görseli çerçeveye ORANI BOZMADAN sığdırmak için kırpma penceresi.

    "kapla" (cover): çerçeve tamamen dolar, taşan kenarlar kırpılır — albüm
    kapağı gibi kare alanlarda istenen davranış budur.
    """
    hedef_w = _sayi(alan.get("w"), 0.3)
    hedef_h = _sayi(alan.get("h"), 0.3)
    if not kaynak_w or not kaynak_h or hedef_h <= 0:
        return None
    # Not: alan oranı BASKI ALANINA oransal olduğu için gerçek en/boy oranı
    # baskı alanının kendi oranıyla çarpılarak bulunur; bu değer çağıranda
    # hesaplanıp "hedef_oran" olarak geçilebilir. Basit hâlde kare kabul edilmez:
    hedef_oran = _sayi(alan.get("_hedef_oran"), hedef_w / hedef_h)
    kaynak_oran = kaynak_w / kaynak_h
    if kaynak_oran > hedef_oran:      # kaynak daha geniş → yanlardan kırp
        w = hedef_oran / kaynak_oran
        return {"x": (1 - w) / 2, "y": 0.0, "w": w, "h": 1.0}
    h = kaynak_oran / hedef_oran      # kaynak daha uzun → üst/alttan kırp
    return {"x": 0.0, "y": (1 - h) / 2, "w": 1.0, "h": h}


def layers_uret(overlay, degerler: dict | None, db=None, alan_oran: float = 1.0) -> list[dict]:
    """Alan değerleri → çizim katmanları (dizideki sıra çizim sırasıdır).

    alan_oran: baskı alanının en/boy oranı (W/H). Fotoğraf çerçevelerinde
    "kapla" hesabı için gerekir; verilmezse kare varsayılır.
    """
    degerler = degerler or {}
    arkadakiler: list[dict] = []      # şablonun ALTINA çizilecekler
    ondekiler: list[dict] = []        # şablonun ÜSTÜNE çizilecekler

    for i, a in enumerate(overlay.alanlar or []):
        anahtar = str(a.get("key") or f"alan{i}")
        tip = a.get("tip")
        hedef = arkadakiler if a.get("arkada") else ondekiler

        if tip == "yazi":
            ham = degerler.get(anahtar)
            metin = str(ham if ham is not None else (a.get("varsayilan") or "")).strip()
            sinir = int(_sayi(a.get("max"), MAX_METIN)) or MAX_METIN
            metin = metin[:min(sinir, MAX_METIN)]
            if not metin:
                continue
            hedef.append({
                "id": f"alan-{anahtar}",
                "type": "text",
                "text": metin,
                "font": str(a.get("font") or "anton"),
                "size": _sayi(a.get("size"), 0.1),
                "color": str(a.get("renk") or "#ffffff"),
                "x": _sayi(a.get("x"), 0.1),
                "y": _sayi(a.get("y"), 0.1),
                "w": _sayi(a.get("w"), 0.8),
                # Çerçeve yüksekliği — panelde çizilmemişse gönderilmez:
                # o alanda metin BÜYÜMEZ, yalnız gerekirse küçülür
                **({"h": _sayi(a.get("h"))} if _sayi(a.get("h")) > 0 else {}),
                "rot": 0,
                "align": str(a.get("hiza") or "center"),
                # Çerçeveye sığdırma: uzun metinde punto otomatik küçülür.
                # Hesap çizim anında yapılır (font ölçüsü orada bilinir).
                "sigdir": a.get("otomatik_kucult", True) is not False,
            })

        elif tip == "gorsel":
            secim = degerler.get(anahtar)
            acik = bool(a.get("varsayilan", True)) if secim is None else bool(secim)
            if not acik or not a.get("image_path"):
                continue
            hedef.append({
                "id": f"alan-{anahtar}",
                "type": "overlay",
                "overlay_id": str(overlay.id),
                "field": anahtar,
            })

        elif tip == "foto":
            # MÜŞTERİNİN yüklediği görsel — çerçeveye otomatik oturur
            asset_id = str(degerler.get(anahtar) or "").strip()
            if not asset_id:
                continue
            crop = None
            if db is not None and str(a.get("sigdir") or "kapla") == "kapla":
                boyut = _asset_boyut(db, asset_id)
                if boyut:
                    hedef_oran = (_sayi(a.get("w"), 0.3) * alan_oran) / max(
                        _sayi(a.get("h"), 0.3), 1e-6)
                    crop = kapla_crop({**a, "_hedef_oran": hedef_oran}, *boyut)
            hedef.append({
                "id": f"alan-{anahtar}",
                "type": "image",
                "asset_id": asset_id,
                "x": _sayi(a.get("x"), 0.1),
                "y": _sayi(a.get("y"), 0.1),
                "w": _sayi(a.get("w"), 0.3),
                "h": _sayi(a.get("h"), 0.3),
                "rot": 0,
                **({"crop": crop} if crop else {}),
            })

        elif tip == "ilerleme":
            # Spotify tarzı çubuk: nokta, geçen/toplam süreye göre kayar
            gecen = saniye_coz(degerler.get(a.get("kaynak_gecen") or ""))
            toplam = saniye_coz(degerler.get(a.get("kaynak_toplam") or ""))
            if gecen is None or toplam is None:
                # Müşteri henüz yazmadıysa alanların varsayılanlarını kullan
                gecen = gecen if gecen is not None else _alan_varsayilan_sn(
                    overlay, a.get("kaynak_gecen"))
                toplam = toplam if toplam is not None else _alan_varsayilan_sn(
                    overlay, a.get("kaynak_toplam"))
            oran = 0.0
            if gecen is not None and toplam:
                oran = max(0.0, min(1.0, gecen / toplam))
            x = _sayi(a.get("x"), 0.1)
            y = _sayi(a.get("y"), 0.5)
            w = _sayi(a.get("w"), 0.8)
            kalinlik = _sayi(a.get("kalinlik"), 0.004)
            boyut = _sayi(a.get("boyut"), 0.012)
            hedef.append({
                "id": f"alan-{anahtar}",
                "type": "sekil",
                "bicim": "ilerleme",
                "x": x, "y": y, "w": w,
                "kalinlik": kalinlik,
                "boyut": boyut,
                "oran": oran,
                "renk": str(a.get("renk") or "#ffffff"),
                "renk_pasif": str(a.get("renk_pasif") or "#5a5a5a"),
            })

    taban = {"id": "taban", "type": "overlay", "overlay_id": str(overlay.id)}
    return [*arkadakiler, taban, *ondekiler]


def _alan_varsayilan_sn(overlay, key) -> float | None:
    for a in overlay.alanlar or []:
        if str(a.get("key")) == str(key):
            return saniye_coz(a.get("varsayilan"))
    return None


def _asset_boyut(db, asset_id: str) -> tuple[int, int] | None:
    from sqlalchemy import select

    from app.models import DesignAsset

    try:
        a = db.scalar(select(DesignAsset).where(DesignAsset.id == asset_id))
    except Exception:  # noqa: BLE001 — geçersiz uuid
        return None
    if not a or not a.width or not a.height:
        return None
    return int(a.width), int(a.height)


def alan_ozeti(overlay) -> list[dict]:
    """Vitrine gönderilecek alan tanımları (müşterinin dolduracağı form)."""
    ozet = []
    for i, a in enumerate(overlay.alanlar or []):
        anahtar = str(a.get("key") or f"alan{i}")
        ortak = {
            "key": anahtar,
            "tip": a.get("tip"),
            "etiket": a.get("etiket") or anahtar,
            "arkada": bool(a.get("arkada")),
            "x": _sayi(a.get("x")), "y": _sayi(a.get("y")),
            "w": _sayi(a.get("w"), 0.8),
        }
        if a.get("tip") == "yazi":
            ozet.append({
                **ortak,
                "varsayilan": a.get("varsayilan") or "",
                "max": int(_sayi(a.get("max"), MAX_METIN)) or MAX_METIN,
                "size": _sayi(a.get("size"), 0.1),
                "font": a.get("font") or "anton",
                "renk": a.get("renk") or "#ffffff",
                "hiza": a.get("hiza") or "center",
                "h": _sayi(a.get("h")) or None,
                "otomatik_kucult": a.get("otomatik_kucult", True) is not False,
            })
        elif a.get("tip") == "gorsel":
            ozet.append({
                **ortak,
                "h": _sayi(a.get("h"), 0.1),
                "varsayilan": bool(a.get("varsayilan", True)),
                "image_url": f"/storage/{a['image_path']}" if a.get("image_path") else None,
            })
        elif a.get("tip") == "foto":
            ozet.append({
                **ortak,
                "h": _sayi(a.get("h"), 0.3),
                "sigdir": a.get("sigdir") or "kapla",
            })
        elif a.get("tip") == "ilerleme":
            ozet.append({
                **ortak,
                "kalinlik": _sayi(a.get("kalinlik"), 0.004),
                "boyut": _sayi(a.get("boyut"), 0.012),
                "renk": a.get("renk") or "#ffffff",
                "renk_pasif": a.get("renk_pasif") or "#5a5a5a",
                "kaynak_gecen": a.get("kaynak_gecen") or "",
                "kaynak_toplam": a.get("kaynak_toplam") or "",
            })
    return ozet
