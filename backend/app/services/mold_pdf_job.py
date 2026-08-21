"""Kalıp PDF'ini ARKA PLANDA üret + sonucu önbellekle.

Neden: bu tasarımlar patolojik derecede karmaşık vektörler ve 22 slotluk bir
kalıp vektör korunarak ~200 sn sürüyor. Rasterleştirmek süreyi düşürürdü ama
matbaa çıktısında vektör kaybına ve saydam kenarlarda bozulmaya yol açıyor —
kabul edilemez. Süre düşürülemiyorsa iş, 100 sn'lik vekil (Cloudflare)
penceresinin DIŞINA alınmalı.

Akış:
  1) istek gelir  -> önbellekte hazır PDF var mı? varsa doğrudan verilir
  2) yoksa        -> arka planda üretim başlar, istek 202 ile döner
  3) panel sorar  -> hazır olunca indirir

Önbellek anahtarı kalıbın İÇERİĞİNDEN türetilir (kalem + tasarım dosyası
kimliği + şablon). Kalıp ya da tasarım değişirse anahtar değişir, bayat PDF
verilmez.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from pathlib import Path

from app.services.storage import STORAGE_ROOT

logger = logging.getLogger("kalip-pdf")

# {anahtar: {"durum": hazirlaniyor|hata, "baslangic": ts, "mesaj": str}}
_isler: dict[str, dict] = {}
_kilit = threading.Lock()

# Üretim bu süreyi aşarsa iş ölmüş sayılır (yeniden denenebilsin)
ZAMAN_ASIMI = 20 * 60


def _dizin() -> Path:
    d = STORAGE_ROOT / "cache" / "kalip_pdf"
    d.mkdir(parents=True, exist_ok=True)
    return d


def anahtar_uret(mold, slot_items: list[dict], template: dict) -> str:
    """Kalıbın içeriğinden kararlı bir anahtar. İçerik değişirse anahtar değişir."""
    h = hashlib.sha256()
    h.update(str(mold.id).encode())
    h.update(str(template.get("page_w_pt")).encode())
    h.update(str(template.get("page_h_pt")).encode())
    h.update(json.dumps(template.get("boxes"), sort_keys=True,
                        default=str).encode())
    for it in sorted(slot_items, key=lambda x: (x.get("slot_index") or 0)):
        h.update(str(it.get("slot_index")).encode())
        h.update(str(it.get("model")).encode())
        h.update(str(it.get("spec")).encode())
        rel = it.get("design_file_path") or ""
        h.update(rel.encode())
        # Tasarım DOSYASI değişirse (aynı yol, yeni içerik) anahtar da değişsin
        try:
            st = (STORAGE_ROOT / rel).stat()
            h.update(f"{st.st_size}:{int(st.st_mtime)}".encode())
        except OSError:
            h.update(b"yok")
    return h.hexdigest()[:32]


def yollar(anahtar: str) -> tuple[Path, Path]:
    d = _dizin()
    return d / f"{anahtar}.pdf", d / f"{anahtar}.json"


def durum(anahtar: str) -> dict:
    """{durum: hazir|hazirlaniyor|hata|yok, ...}"""
    pdf, meta = yollar(anahtar)
    if pdf.exists():
        try:
            rapor = json.loads(meta.read_text(encoding="utf-8")) if meta.exists() else {}
        except Exception:  # noqa: BLE001
            rapor = {}
        return {"durum": "hazir", "boyut": pdf.stat().st_size, "rapor": rapor}
    with _kilit:
        i = _isler.get(anahtar)
    if i:
        if i["durum"] == "hata":
            return {"durum": "hata", "mesaj": i.get("mesaj") or "Üretim başarısız"}
        if time.time() - i["baslangic"] < ZAMAN_ASIMI:
            return {"durum": "hazirlaniyor",
                    "gecen_sn": int(time.time() - i["baslangic"])}
    return {"durum": "yok"}


def _uret(anahtar: str, slot_items: list[dict], template: dict) -> None:
    from app.services import mold_pdf
    pdf, meta = yollar(anahtar)
    try:
        veri, rapor = mold_pdf.render_mold_pdf(slot_items, template=template)
        # Atomik yazım: yarım dosya indirilmesin
        gecici = pdf.with_suffix(".pdf.tmp")
        gecici.write_bytes(veri)
        meta.write_text(json.dumps(rapor, default=str), encoding="utf-8")
        gecici.replace(pdf)
        logger.info("[kalip-pdf] hazir: %s (%.1f MB)", anahtar, len(veri) / 1024 / 1024)
        with _kilit:
            _isler.pop(anahtar, None)
    except Exception as e:  # noqa: BLE001
        logger.exception("[kalip-pdf] uretim hatasi: %s", e)
        with _kilit:
            _isler[anahtar] = {"durum": "hata", "baslangic": time.time(),
                               "mesaj": str(e)[:200]}


def baslat(arka_plan, anahtar: str, slot_items: list[dict], template: dict) -> bool:
    """Üretimi arka planda başlat. Zaten çalışıyorsa False."""
    with _kilit:
        i = _isler.get(anahtar)
        if i and i["durum"] == "hazirlaniyor" and time.time() - i["baslangic"] < ZAMAN_ASIMI:
            return False
        _isler[anahtar] = {"durum": "hazirlaniyor", "baslangic": time.time()}
    arka_plan.add_task(_uret, anahtar, slot_items, template)
    return True


def temizle(gun: int = 7) -> int:
    """Eski önbellek dosyalarını sil. Dönüş: silinen dosya sayısı."""
    d = _dizin()
    esik = time.time() - gun * 86400
    n = 0
    for p in d.iterdir():
        try:
            if p.is_file() and p.stat().st_mtime < esik:
                p.unlink()
                n += 1
        except OSError:
            pass
    return n
