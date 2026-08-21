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


def yollar(mold_id, anahtar: str) -> tuple[Path, Path]:
    """Dosya adı kalıp kimliğiyle başlar — bir kalıbın TÜM hazır PDF'leri
    (eski anahtarlar dahil) tek desenle bulunup silinebilsin."""
    d = _dizin()
    return d / f"{mold_id}_{anahtar}.pdf", d / f"{mold_id}_{anahtar}.json"


def gecersiz_kil(mold_id) -> int:
    """Kalıbın hazırlanmış PDF'lerini sil. Kalıp DEĞİŞTİĞİNDE çağrılır.

    Anahtar içerikten türediği için bayat bir PDF zaten SUNULMAZ; bu silme
    diski temiz tutmak ve panelde "PDF yok" durumunun görünmesi için.
    """
    n = 0
    for p in _dizin().glob(f"{mold_id}_*"):
        try:
            p.unlink()
            n += 1
        except OSError:
            pass
    with _kilit:
        for k in [k for k, v in _isler.items() if v.get("mold_id") == str(mold_id)]:
            _isler.pop(k, None)
    return n


def durum(mold_id, anahtar: str) -> dict:
    """{durum: hazir|hazirlaniyor|hata|yok, ...}"""
    pdf, meta = yollar(mold_id, anahtar)
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


def _uret(mold_id, anahtar: str, slot_items: list[dict], template: dict) -> None:
    from app.services import mold_pdf
    pdf, meta = yollar(mold_id, anahtar)
    _t0 = time.time()
    logger.info("[kalip-pdf] uretim BASLADI: kalip=%s slot=%s", mold_id, len(slot_items))
    try:
        veri, rapor = mold_pdf.render_mold_pdf(slot_items, template=template)
        # Atomik yazım: yarım dosya indirilmesin
        gecici = pdf.with_suffix(".pdf.tmp")
        gecici.write_bytes(veri)
        meta.write_text(json.dumps(rapor, default=str), encoding="utf-8")
        gecici.replace(pdf)
        logger.info("[kalip-pdf] HAZIR: kalip=%s %.1f MB %.0f sn",
                    mold_id, len(veri) / 1024 / 1024, time.time() - _t0)
        with _kilit:
            _isler.pop(anahtar, None)
    except Exception as e:  # noqa: BLE001
        logger.exception("[kalip-pdf] HATA: kalip=%s (%.0f sn) %s",
                         mold_id, time.time() - _t0, e)
        with _kilit:
            _isler[anahtar] = {"durum": "hata", "baslangic": time.time(),
                               "mesaj": str(e)[:200]}


def baslat(arka_plan, mold_id, anahtar: str, slot_items: list[dict],
           template: dict) -> bool:
    """Üretimi arka planda başlat. Zaten çalışıyorsa False."""
    with _kilit:
        i = _isler.get(anahtar)
        if i and i["durum"] == "hazirlaniyor" and time.time() - i["baslangic"] < ZAMAN_ASIMI:
            return False
        _isler[anahtar] = {"durum": "hazirlaniyor", "baslangic": time.time(),
                           "mold_id": str(mold_id)}
    arka_plan.add_task(_uret, mold_id, anahtar, slot_items, template)
    return True


def kuyruk() -> list[dict]:
    """Şu an üretimi süren işler. Panel bunu sorar — hangi kalıpları soracağını
    bilmesi gerekmez, sunucu ne çalışıyorsa onu söyler."""
    simdi = time.time()
    out = []
    with _kilit:
        for anahtar, i in list(_isler.items()):
            if i.get("durum") != "hazirlaniyor":
                continue
            if simdi - i["baslangic"] >= ZAMAN_ASIMI:
                continue
            out.append({"mold_id": i.get("mold_id"), "anahtar": anahtar,
                        "gecen_sn": int(simdi - i["baslangic"])})
    out.sort(key=lambda x: -x["gecen_sn"])
    return out


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
