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

import contextlib
import fcntl
import hashlib
import json
import logging
import os
import time
from pathlib import Path

from app.services.storage import STORAGE_ROOT

logger = logging.getLogger("kalip-pdf")

# ⚠ İŞ KAYDI DOSYADA, SÜREÇ BELLEĞİNDE DEĞİL. Eskiden `_isler` bir sözlüktü:
# tek uvicorn worker'ında doğru, ama ikinci worker açıldığı gün A worker'ının
# başlattığı üretimi B worker'ı "yok" görüyor, panelin tekrar isteğiyle AYNI
# 3-4 dakikalık CPU işini ikinci kez başlatıyor ve kuyruk listesi hangi
# worker'a düştüğüne göre boş/dolu görünüyordu. Kayıt `<kalıp>_<anahtar>.is`
# dosyası; oku-karar-yaz bölümü süreçler arası dosya kilidiyle korunur.
#
# İçerik: {"durum": hazirlaniyor|hata, "baslangic", "kuyruga_alindi",
#          "basladi", "mold_id", "pid", "mesaj"}

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


def _is_yolu(mold_id, anahtar: str) -> Path:
    return _dizin() / f"{mold_id}_{anahtar}.is"


@contextlib.contextmanager
def _surecler_arasi_kilit():
    """Oku-karar-yaz bölümü: aynı anda yalnız BİR süreç (worker) girer."""
    with open(_dizin() / ".is-kilidi", "w") as fd:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)


def _is_oku(yol: Path) -> dict | None:
    try:
        return json.loads(yol.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _is_yaz(yol: Path, kayit: dict) -> None:
    """Atomik yazım — yarım okunan JSON olmasın."""
    gecici = yol.with_suffix(".is.tmp")
    gecici.write_text(json.dumps(kayit), encoding="utf-8")
    gecici.replace(yol)


def _surec_yasiyor(pid) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, TypeError, ValueError):
        return False


def _canli_mi(i: dict | None, simdi: float) -> bool:
    """İş hâlâ gerçekten sürüyor mu?

    ⚠ Bellekteki kayıt süreçle birlikte ölüyordu; dosyadaki kayıt ÖLMEZ. Worker
    yeniden başlatılınca (deploy) sırada bekleyen iş sonsuza dek "hazırlanıyor"
    görünüp PDF hiç üretilmezdi. Sahibi süreç ölmüşse iş ölü sayılır.
    """
    if not i or i.get("durum") != "hazirlaniyor":
        return False
    if i.get("pid") is not None and not _surec_yasiyor(i["pid"]):
        return False
    if i.get("basladi"):
        return simdi - i.get("baslangic", 0) < ZAMAN_ASIMI
    # Sırada bekleyen iş, önündeki uzun işler yüzünden bekleyebilir — ama sınırsız değil.
    return simdi - i.get("kuyruga_alindi", i.get("baslangic", 0)) < 2 * ZAMAN_ASIMI


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
    # `.is` iş kayıtları da aynı desene uyar — ayrıca temizlemek gerekmez.
    for p in _dizin().glob(f"{mold_id}_*"):
        try:
            p.unlink()
            n += 1
        except OSError:
            pass
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
    i = _is_oku(_is_yolu(mold_id, anahtar))
    if i:
        if i.get("durum") == "hata":
            return {"durum": "hata", "mesaj": i.get("mesaj") or "Üretim başarısız"}
        simdi = time.time()
        if _canli_mi(i, simdi):
            return {"durum": "hazirlaniyor",
                    "basladi": bool(i.get("basladi")),
                    "gecen_sn": int(simdi - i.get("baslangic", simdi))}
    return {"durum": "yok"}


def _uret(mold_id, anahtar: str, slot_items: list[dict], template: dict) -> None:
    from app.services import mold_pdf
    pdf, meta = yollar(mold_id, anahtar)
    _t0 = time.time()
    is_yolu = _is_yolu(mold_id, anahtar)
    with _surecler_arasi_kilit():
        i = _is_oku(is_yolu)
        if i is not None:
            i["baslangic"] = _t0        # kuyrukta bekleme suresi sayilmasin
            i["basladi"] = True
            i["pid"] = os.getpid()      # üretimi GERÇEKTEN yapan süreç
            _is_yaz(is_yolu, i)
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
        is_yolu.unlink(missing_ok=True)
    except Exception as e:  # noqa: BLE001
        logger.exception("[kalip-pdf] HATA: kalip=%s (%.0f sn) %s",
                         mold_id, time.time() - _t0, e)
        with _surecler_arasi_kilit():
            _is_yaz(is_yolu, {"durum": "hata", "baslangic": time.time(),
                              "mold_id": str(mold_id), "mesaj": str(e)[:200]})


def baslat(arka_plan, mold_id, anahtar: str, slot_items: list[dict],
           template: dict) -> bool:
    """Üretimi arka planda başlat. Zaten (herhangi bir worker'da) çalışıyorsa False."""
    is_yolu = _is_yolu(mold_id, anahtar)
    with _surecler_arasi_kilit():
        simdi = time.time()
        if _canli_mi(_is_oku(is_yolu), simdi):
            return False
        _is_yaz(is_yolu, {"durum": "hazirlaniyor", "baslangic": simdi,
                          "kuyruga_alindi": simdi, "basladi": False,
                          "mold_id": str(mold_id), "pid": os.getpid()})
    arka_plan.add_task(_uret, mold_id, anahtar, slot_items, template)
    return True


def kuyruk() -> list[dict]:
    """Şu an üretimi süren işler. Panel bunu sorar — hangi kalıpları soracağını
    bilmesi gerekmez, sunucu ne çalışıyorsa onu söyler."""
    simdi = time.time()
    out = []
    for yol in _dizin().glob("*.is"):
        i = _is_oku(yol)
        if not _canli_mi(i, simdi):
            continue
        # Dosya adı "<kalıp>_<anahtar>.is" — anahtar alt çizgi içermez.
        anahtar = yol.stem.rsplit("_", 1)[-1]
        out.append({"mold_id": i.get("mold_id"), "anahtar": anahtar,
                    "gecen_sn": int(simdi - i.get("baslangic", simdi))})
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
