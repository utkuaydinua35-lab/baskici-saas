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

⚠ ÜRETİM AYRI BİR SÜREÇTE (2026-09-11). Eskiden uvicorn worker'ının içinde
(thread havuzunda) çalışıyordu. `--workers 2` açılınca uvicorn'un ebeveyn
süreci her worker'a 5 sn'de bir "yaşıyor musun" diye soruyor; PyMuPDF uzun
vektör çizimlerinde Python kilidini (GIL) bırakmadığı için worker cevap
veremiyor, ebeveyn onu "askıda" sayıp ÖLDÜRÜYORDU — üretim başladıktan ~20 sn
sonra, her seferinde. İş kaydının sahibi öldüğü için durum "yok"a dönüyor,
panelde her tıklama üretimi baştan başlatıyor ve PDF hiç inmiyordu.
Artık worker yalnız bir çocuk süreç başlatıp bekliyor; çizimi çocuk yapıyor.
Worker'ın kilidi hep boş, sağlık kontrolüne cevap veriyor; worker yine de
ölürse çocuk kendi oturumunda olduğu için işini bitirip PDF'i yazıyor.
"""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import logging
import os
import signal
import subprocess
import sys
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
# `pid`: kuyruktayken işi sıraya alan worker; üretim başlayınca ÇİZİMİ YAPAN
# çocuk süreç.

# Üretim bu süreyi aşarsa iş ölmüş sayılır (yeniden denenebilsin)
ZAMAN_ASIMI = 20 * 60

# backend/ kökü — çocuk süreç `python -m app.services...` ile buradan başlar.
_BACKEND_KOK = Path(__file__).resolve().parents[2]


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


def _girdi_yolu(mold_id, anahtar: str) -> Path:
    """Çocuk sürece verilen üretim girdisi (slot'lar + şablon)."""
    return _dizin() / f"{mold_id}_{anahtar}.girdi"


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
        pid = int(pid)
        os.kill(pid, 0)
    except (OSError, TypeError, ValueError):
        return False
    # Bitmiş ama ebeveyni henüz toplamamış süreç (zombi) kill(0)'a "yaşıyor"
    # der — iş 20 dk boyunca "hazırlanıyor" görünürdü. Kendi çocuğumuzsa topla;
    # Linux'ta /proc'tan durumuna bak.
    try:
        bitti, _ = os.waitpid(pid, os.WNOHANG)
        if bitti == pid:
            return False
    except OSError:
        pass                                  # bizim çocuğumuz değil
    try:
        with open(f"/proc/{pid}/stat", "rb") as f:
            # "pid (ad) DURUM ..." — ad boşluk/parantez içerebilir; son ')' sonrası
            if f.read().rsplit(b")", 1)[1].split()[0] == b"Z":
                return False
    except (OSError, IndexError):
        pass
    return True


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


def _takilan_cocugu_durdur(i: dict | None) -> None:
    """Zaman aşımına uğramış ama süreci hâlâ yaşayan üretimi durdur — yeniden
    başlatılan iş, takılı kalanla aynı anda bir CPU çekirdeğini daha yemesin.
    Yalnız GERÇEKTEN bizim üretim sürecimizse (pid başka bir sürece geçmiş
    olabilir): Linux'ta komut satırından doğrulanır, doğrulanamazsa dokunulmaz."""
    if not i or not i.get("basladi") or not i.get("pid"):
        return
    pid = int(i["pid"])
    if pid == os.getpid() or not _surec_yasiyor(pid):
        return
    try:
        komut = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return
    if b"mold_pdf_job" in komut:
        with contextlib.suppress(OSError):
            os.kill(pid, signal.SIGKILL)
            logger.warning("[kalip-pdf] takılan üretim süreci durduruldu: pid=%s", pid)


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
    # `.is` iş kayıtları ve `.girdi` dosyaları da aynı desene uyar.
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


def _hata_yaz(mold_id, anahtar: str, mesaj: str, yalniz_suruyorsa: bool = False) -> None:
    is_yolu = _is_yolu(mold_id, anahtar)
    with _surecler_arasi_kilit():
        if yalniz_suruyorsa:
            i = _is_oku(is_yolu)
            if not i or i.get("durum") != "hazirlaniyor":
                return
        _is_yaz(is_yolu, {"durum": "hata", "baslangic": time.time(),
                          "mold_id": str(mold_id), "mesaj": mesaj[:200]})


def _uret(mold_id, anahtar: str, slot_items: list[dict], template: dict) -> None:
    """Worker tarafı: üretimi AYRI SÜREÇTE başlat ve bitmesini bekle.

    Beklemek kuyruğu SIRALI tutar (toplu hazırlamada kalıplar aynı anda değil
    art arda üretilir — bellek). Bekleyen worker ölürse çocuk etkilenmez.
    """
    is_yolu = _is_yolu(mold_id, anahtar)
    try:
        _girdi_yolu(mold_id, anahtar).write_text(
            json.dumps({"slot_items": slot_items, "template": template}, default=str),
            encoding="utf-8")
        cocuk = subprocess.Popen(
            [sys.executable, "-m", "app.services.mold_pdf_job", str(mold_id), anahtar],
            cwd=str(_BACKEND_KOK),
            stdin=subprocess.DEVNULL,
            # Kendi oturumu: worker'a gelen sinyal (sağlık kontrolü öldürmesi)
            # çocuğa geçmez. Servis durdurulunca systemd yine hepsini kapatır.
            start_new_session=True,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("[kalip-pdf] üretim süreci başlatılamadı: kalip=%s", mold_id)
        _hata_yaz(mold_id, anahtar, f"Üretim başlatılamadı: {e}")
        return

    # pid'i HEMEN yaz: çocuk açılırken (import ~1 sn) worker ölürse iş sahipsiz
    # görünmesin. Çocuk başlayınca kendi de yazar.
    with _surecler_arasi_kilit():
        i = _is_oku(is_yolu)
        if i is not None and i.get("durum") == "hazirlaniyor":
            i.update(baslangic=time.time(), basladi=True, pid=cocuk.pid)
            _is_yaz(is_yolu, i)
    logger.info("[kalip-pdf] ayrı süreçte başlatıldı: kalip=%s pid=%s", mold_id, cocuk.pid)

    kod = cocuk.wait()
    pdf, _ = yollar(mold_id, anahtar)
    if not pdf.exists():
        # Çocuk hata YAZAMADAN öldüyse (bellek yetmedi, dışarıdan öldürüldü)
        # kayıt "hazırlanıyor"da kalır; sessizce yeniden başlamak yerine sebebi göster.
        _hata_yaz(mold_id, anahtar,
                  f"PDF üretimi yarıda kesildi (çıkış kodu {kod}). "
                  "'PDF Hazırla' ile tekrar deneyin.",
                  yalniz_suruyorsa=True)


def _cocuk_calis(mold_id: str, anahtar: str) -> int:
    """Çocuk süreç: PDF'i çiz, yaz, kaydı kapat."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    # API worker'larından CPU çalmasın — üretim 3-4 dk bir çekirdeği dolduruyor.
    with contextlib.suppress(OSError):
        os.nice(10)
    is_yolu = _is_yolu(mold_id, anahtar)
    girdi = _girdi_yolu(mold_id, anahtar)
    pdf, meta = yollar(mold_id, anahtar)
    _t0 = time.time()
    with _surecler_arasi_kilit():
        i = _is_oku(is_yolu)
        if i is not None and i.get("durum") == "hazirlaniyor":
            i.update(baslangic=_t0, basladi=True, pid=os.getpid())
            _is_yaz(is_yolu, i)
    try:
        # Tasarım yavaşlığını taklit etmek için (yalnız test): üretimde çizim
        # 200 sn sürüyor, testte worker'ı çizim SIRASINDA öldürebilmek gerekiyor.
        gecikme = float(os.environ.get("KALIP_PDF_TEST_GECIKME_SN") or 0)
        if gecikme > 0:
            time.sleep(gecikme)
        g = json.loads(girdi.read_text(encoding="utf-8"))
        slot_items, template = g["slot_items"], g["template"]
        for it in slot_items:
            # JSON demeti listeye çeviriyor; ölçü (en, boy, köşe) demet bekleniyor.
            if isinstance(it.get("spec"), list):
                it["spec"] = tuple(it["spec"])
        from app.services import mold_pdf
        logger.info("[kalip-pdf] uretim BASLADI: kalip=%s slot=%s pid=%s",
                    mold_id, len(slot_items), os.getpid())
        veri, rapor = mold_pdf.render_mold_pdf(slot_items, template=template)
        # Atomik yazım: yarım dosya indirilmesin
        gecici = pdf.with_suffix(".pdf.tmp")
        gecici.write_bytes(veri)
        meta.write_text(json.dumps(rapor, default=str), encoding="utf-8")
        gecici.replace(pdf)
        logger.info("[kalip-pdf] HAZIR: kalip=%s %.1f MB %.0f sn",
                    mold_id, len(veri) / 1024 / 1024, time.time() - _t0)
        is_yolu.unlink(missing_ok=True)
        return 0
    except Exception as e:  # noqa: BLE001
        logger.exception("[kalip-pdf] HATA: kalip=%s (%.0f sn) %s",
                         mold_id, time.time() - _t0, e)
        _hata_yaz(mold_id, anahtar, str(e))
        return 1
    finally:
        girdi.unlink(missing_ok=True)


def baslat(arka_plan, mold_id, anahtar: str, slot_items: list[dict],
           template: dict) -> bool:
    """Üretimi arka planda başlat. Zaten (herhangi bir worker'da) çalışıyorsa False."""
    is_yolu = _is_yolu(mold_id, anahtar)
    with _surecler_arasi_kilit():
        simdi = time.time()
        eski = _is_oku(is_yolu)
        if _canli_mi(eski, simdi):
            return False
        _takilan_cocugu_durdur(eski)
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


if __name__ == "__main__":
    # `python -m app.services.mold_pdf_job <kalıp_id> <anahtar>` — _uret başlatır.
    sys.exit(_cocuk_calis(sys.argv[1], sys.argv[2]))
