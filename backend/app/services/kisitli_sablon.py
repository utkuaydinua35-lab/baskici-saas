"""Kısıtlı hazır şablon — müşteri yalnız tanımlı alanları doldurur.

Örnek: forma tasarımı. Zemin (çizgiler, arma) SABİTTİR; müşteri sadece
numarayı ve ismi yazar, bayrak/logo gibi öğeleri açıp kapatır. Görsel yükleyip
yazı ekleyemez, hiçbir şeyi taşıyamaz.

Bu modül alan DEĞERLERİNDEN çizim katmanlarını üretir. Konum, font, renk, punto
ve dosya yolları HEP ŞABLONDAN gelir; müşteriden sadece metin ve aç/kapa
alınır. Katmanlar sunucuda burada üretildiği için müşteri gövdeyi değiştirse
bile baskıya şablonun dışına çıkan bir şey giremez.

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


def layers_uret(overlay, degerler: dict | None) -> list[dict]:
    """Alan değerleri → çizim katmanları (dizideki sıra çizim sırasıdır)."""
    degerler = degerler or {}
    # Zemin: şablonun kendi görseli, en altta
    katmanlar: list[dict] = [
        {"id": "taban", "type": "overlay", "overlay_id": str(overlay.id)}
    ]

    for i, a in enumerate(overlay.alanlar or []):
        anahtar = str(a.get("key") or f"alan{i}")
        tip = a.get("tip")

        if tip == "yazi":
            ham = degerler.get(anahtar)
            metin = str(ham if ham is not None else (a.get("varsayilan") or "")).strip()
            sinir = int(_sayi(a.get("max"), MAX_METIN)) or MAX_METIN
            metin = metin[:min(sinir, MAX_METIN)]
            if not metin:
                continue
            katmanlar.append({
                "id": f"alan-{anahtar}",
                "type": "text",
                "text": metin,
                "font": str(a.get("font") or "anton"),
                "size": _sayi(a.get("size"), 0.1),
                "color": str(a.get("renk") or "#ffffff"),
                "x": _sayi(a.get("x"), 0.1),
                "y": _sayi(a.get("y"), 0.1),
                "w": _sayi(a.get("w"), 0.8),
                "rot": 0,
                "align": str(a.get("hiza") or "center"),
            })

        elif tip == "gorsel":
            secim = degerler.get(anahtar)
            acik = bool(a.get("varsayilan", True)) if secim is None else bool(secim)
            if not acik or not a.get("image_path"):
                continue
            # Alan görselinin dosya yolu şablondan okunur (render tarafında da
            # DB'den doğrulanır) — müşteri kendi url'ini bastıramaz.
            katmanlar.append({
                "id": f"alan-{anahtar}",
                "type": "overlay",
                "overlay_id": str(overlay.id),
                "field": anahtar,
            })

    return katmanlar


def alan_ozeti(overlay) -> list[dict]:
    """Vitrine gönderilecek alan tanımları (müşterinin dolduracağı form)."""
    ozet = []
    for i, a in enumerate(overlay.alanlar or []):
        anahtar = str(a.get("key") or f"alan{i}")
        ortak = {
            "key": anahtar,
            "tip": a.get("tip"),
            "etiket": a.get("etiket") or anahtar,
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
            })
        elif a.get("tip") == "gorsel":
            ozet.append({
                **ortak,
                "h": _sayi(a.get("h"), 0.1),
                "varsayilan": bool(a.get("varsayilan", True)),
                "image_url": f"/storage/{a['image_path']}" if a.get("image_path") else None,
            })
    return ozet
