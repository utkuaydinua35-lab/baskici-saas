"""Zamanlanmış veritabanı yedeği — pg_dump + gzip + rotasyon.

Yedekler STORAGE_ROOT DIŞINDA tutulur (STORAGE_ROOT /storage'tan public servis
edilir; yedekler tüm veriyi içerir, asla web'e açılmamalı). Sadece platform
admin endpoint'i (auth) ile listelenir/indirilir.

BACKUP_DIR env ile override edilebilir. pg_dump PATH'te olmalı (postgresql-client).
"""
from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.services.storage import STORAGE_ROOT

logger = logging.getLogger("backup")
_TR = ZoneInfo("Europe/Istanbul")

# STORAGE_ROOT'un YANINDA (içinde değil) — web'e açık /storage'a düşmesin
BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", str(STORAGE_ROOT.parent / "backups")))
KEEP = int(os.environ.get("BACKUP_KEEP", "7"))
_NAME_RE = re.compile(r"^baskici-\d{8}-\d{6}\.sql\.gz$")

# ─── TAM YEDEK (veritabanı + dosyalar) ────────────────────────────────────
# ⚠ NEDEN AYRI: gecelik yedek yalnız VERİTABANINI alıyor ve AYNI DİSKTE
# duruyor. Disk ölürse hem veri hem yedek gider; üstelik 6+ GB tasarım/PDF
# dosyası (storage) HİÇ yedeklenmiyordu — onlar olmadan bir sipariş yeniden
# basılamaz. Tam yedek, tek dosyada taşınabilir ve TEK KOMUTLA geri yüklenir.
TAM_KEEP = int(os.environ.get("FULL_BACKUP_KEEP", "2"))
_TAM_RE = re.compile(r"^tam-yedek-\d{8}-\d{6}\.tar$")

# Arşive GİRMEYEN dizinler — yeniden üretilebilir, yeri boşuna şişirir.
# kalip_pdf tek başına 1.2 GB; kalıp PDF'i veritabanındaki plandan yeniden
# üretiliyor (3-4 dk). Geri yüklemede kaybı sadece zaman.
TAM_HARIC = ("cache",)


class BackupError(Exception):
    pass


def _pg_url() -> str:
    """SQLAlchemy URL'inden pg_dump için saf postgresql:// URI."""
    return get_settings().database_url.replace("+psycopg2", "").replace("+psycopg", "")


def _rotate() -> None:
    files = sorted(
        (p for p in BACKUP_DIR.glob("baskici-*.sql.gz") if p.is_file()),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )
    for old in files[KEEP:]:
        try:
            old.unlink()
        except OSError:
            pass


def run_backup() -> dict:
    """pg_dump | gzip -> BACKUP_DIR/baskici-<ts>.sql.gz, rotasyon. Dosya bilgisi döner."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(_TR).strftime("%Y%m%d-%H%M%S")
    out = BACKUP_DIR / f"baskici-{ts}.sql.gz"
    url = _pg_url()
    try:
        with gzip.open(out, "wb") as gz:
            proc = subprocess.Popen(
                ["pg_dump", "--dbname", url, "--no-owner", "--no-privileges"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            shutil.copyfileobj(proc.stdout, gz)
            proc.stdout.close()
            rc = proc.wait()
            err = (proc.stderr.read() or b"").decode(errors="replace")
    except FileNotFoundError as e:
        out.unlink(missing_ok=True)
        raise BackupError("pg_dump bulunamadı. VPS'te 'postgresql-client' kurulu olmalı.") from e
    except Exception as e:  # noqa: BLE001
        out.unlink(missing_ok=True)
        raise BackupError(f"Yedek alınamadı: {e}") from e

    if rc != 0 or not out.exists() or out.stat().st_size == 0:
        out.unlink(missing_ok=True)
        raise BackupError(f"pg_dump hata (kod {rc}): {err[:200]}")

    _rotate()
    size = out.stat().st_size
    logger.info(f"[backup] alındı: {out.name} ({size} bayt)")
    return {"name": out.name, "size": size}


def list_backups() -> list[dict]:
    if not BACKUP_DIR.exists():
        return []
    rows = []
    for p in BACKUP_DIR.glob("baskici-*.sql.gz"):
        if not p.is_file():
            continue
        st = p.stat()
        rows.append({
            "name": p.name,
            "size": st.st_size,
            "created_at": datetime.fromtimestamp(st.st_mtime, _TR).isoformat(),
        })
    rows.sort(key=lambda r: r["created_at"], reverse=True)
    return rows


def backup_path(name: str) -> Path | None:
    """Güvenli dosya yolu (path traversal'a karşı isim doğrulanır)."""
    if not _NAME_RE.match(name or ""):
        return None
    p = (BACKUP_DIR / name).resolve()
    if p.parent != BACKUP_DIR.resolve() or not p.is_file():
        return None
    return p


def _sha256(yol: Path) -> str:
    h = hashlib.sha256()
    with open(yol, "rb") as f:
        for parca in iter(lambda: f.read(1024 * 1024), b""):
            h.update(parca)
    return h.hexdigest()


def _manifest(sql_gz: Path, ts: str) -> dict:
    dosya_sayisi = toplam = 0
    for kok, dizinler, dosyalar in os.walk(STORAGE_ROOT):
        dizinler[:] = [d for d in dizinler
                       if Path(kok) != STORAGE_ROOT or d not in TAM_HARIC]
        for d in dosyalar:
            try:
                toplam += (Path(kok) / d).stat().st_size
                dosya_sayisi += 1
            except OSError:
                pass
    return {
        "surum": 1,
        "olusturuldu": datetime.now(_TR).isoformat(),
        "damga": ts,
        "veritabani_gz_bayt": sql_gz.stat().st_size,
        "veritabani_sha256": _sha256(sql_gz),
        "storage_dosya_sayisi": dosya_sayisi,
        "storage_bayt": toplam,
        "haric_tutulan": list(TAM_HARIC),
        "not": ("cache/ arşive dahil değildir: kalıp PDF'leri veritabanındaki "
                "plandan yeniden üretilir."),
    }


_BENIOKU = """TAM YEDEK — BERNZ / baskıcı
===========================

Bu dosya sistemin TAMAMINI içerir:
  · veritabani.sql.gz  — tüm siparişler, kalıplar, ayarlar, kullanıcılar
  · storage/           — tasarım dosyaları, PDF'ler, mockuplar, yazıcı sertifikası
  · MANIFEST.json      — ne zaman alındı, kaç dosya, doğrulama özeti
  · GERI-YUKLE.sh      — tek komutluk geri yükleme betiği

DAHİL DEĞİL: cache/ (kalıp PDF'leri). Bunlar veritabanındaki plandan yeniden
üretilir; geri yüklemede kaybı yalnızca zamandır.

GERİ YÜKLEME (sunucuda, root olarak)
------------------------------------
    tar -xf tam-yedek-....tar GERI-YUKLE.sh
    sudo bash GERI-YUKLE.sh tam-yedek-....tar --onayliyorum

--onayliyorum yazmazsan hiçbir şeye dokunmaz, sadece ne yapacağını anlatır.

⚠ Geri yükleme MEVCUT VERİYİ SİLER. Mevcut dosya dizini silinmez,
storage.eski-<zaman> olarak saklanır.

İNDİRDİKTEN SONRA DOĞRULAMA
---------------------------
Yanındaki .sha256 dosyasıyla:
    shasum -a 256 -c tam-yedek-....tar.sha256      (Mac)
    sha256sum -c tam-yedek-....tar.sha256          (Linux)
"""


def run_full_backup() -> dict:
    """Veritabanı + dosyaları TEK ARŞİVDE topla. Dosya bilgisi döner.

    Arşiv sıkıştırılmaz (.tar): içerik zaten JPG/PNG/PDF, yani sıkıştırılmış.
    gzip'lemek CPU'yu yakıp ~%2 kazandırırdı. SQL dökümü içeride ayrıca
    gzip'li duruyor.
    """
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(_TR).strftime("%Y%m%d-%H%M%S")
    hedef = BACKUP_DIR / f"tam-yedek-{ts}.tar"
    gecici = BACKUP_DIR / f".tam-{ts}"
    gecici.mkdir(parents=True, exist_ok=True)

    try:
        # 1) Veritabanı
        sql_gz = gecici / "veritabani.sql.gz"
        with gzip.open(sql_gz, "wb") as gz:
            proc = subprocess.Popen(
                ["pg_dump", "--dbname", _pg_url(), "--no-owner", "--no-privileges"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            shutil.copyfileobj(proc.stdout, gz)
            proc.stdout.close()
            rc = proc.wait()
            err = (proc.stderr.read() or b"").decode(errors="replace")
        if rc != 0 or sql_gz.stat().st_size == 0:
            raise BackupError(f"pg_dump hata (kod {rc}): {err[:200]}")

        # 2) Bilgi dosyaları — arşivin kendi kendine yeter olması için
        (gecici / "MANIFEST.json").write_text(
            json.dumps(_manifest(sql_gz, ts), ensure_ascii=False, indent=2),
            encoding="utf-8")
        (gecici / "BENIOKU.txt").write_text(_BENIOKU, encoding="utf-8")
        betik = Path(__file__).resolve().parent.parent.parent / "scripts" / "geri_yukle.sh"
        if betik.exists():
            shutil.copy2(betik, gecici / "GERI-YUKLE.sh")

        # 3) Tek arşiv: önce bilgi dosyaları (arşivin BAŞINDA olsunlar ki
        #    6 GB'ı açmadan okunabilsinler), sonra storage.
        # ⚠ --exclude'lar operandlardan ÖNCE gelmeli: BSD tar (macOS) sonrasında
        # gelenleri dosya adı sanıp "Cannot stat" ile patlıyor. GNU tar (VPS)
        # her iki sırayı da kabul ediyor; taşınabilir olan bu.
        komut = ["tar", "-cf", str(hedef)]
        for h in TAM_HARIC:
            komut.append(f"--exclude={STORAGE_ROOT.name}/{h}")
        komut += ["-C", str(gecici),
                  "veritabani.sql.gz", "MANIFEST.json", "BENIOKU.txt"]
        if (gecici / "GERI-YUKLE.sh").exists():
            komut.append("GERI-YUKLE.sh")
        komut += ["-C", str(STORAGE_ROOT.parent), STORAGE_ROOT.name]
        r = subprocess.run(komut, capture_output=True, text=True)
        if r.returncode != 0 or not hedef.exists():
            hedef.unlink(missing_ok=True)
            raise BackupError(f"Arşiv oluşturulamadı: {(r.stderr or '')[:200]}")

        # 4) İndirdikten sonra doğrulanabilsin
        ozet = _sha256(hedef)
        (BACKUP_DIR / f"{hedef.name}.sha256").write_text(
            f"{ozet}  {hedef.name}\n", encoding="utf-8")
    finally:
        shutil.rmtree(gecici, ignore_errors=True)

    _rotate_full()
    logger.info(f"[backup] tam yedek: {hedef.name} ({hedef.stat().st_size} bayt)")
    return {"name": hedef.name, "size": hedef.stat().st_size, "sha256": ozet}


def _rotate_full() -> None:
    """Tam yedekler BÜYÜK (GB'lar). Diski doldurmamak için az sayıda tutulur."""
    files = sorted((p for p in BACKUP_DIR.glob("tam-yedek-*.tar") if p.is_file()),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[TAM_KEEP:]:
        try:
            old.unlink()
            Path(f"{old}.sha256").unlink(missing_ok=True)
        except OSError:
            pass


def list_full_backups() -> list[dict]:
    if not BACKUP_DIR.exists():
        return []
    rows = []
    for p in BACKUP_DIR.glob("tam-yedek-*.tar"):
        if not p.is_file():
            continue
        st = p.stat()
        ozet = ""
        try:
            ozet = (BACKUP_DIR / f"{p.name}.sha256").read_text(
                encoding="utf-8").split()[0]
        except OSError:
            pass
        rows.append({"name": p.name, "size": st.st_size, "sha256": ozet,
                     "created_at": datetime.fromtimestamp(st.st_mtime, _TR).isoformat()})
    rows.sort(key=lambda r: r["created_at"], reverse=True)
    return rows


def full_backup_path(name: str) -> Path | None:
    """Ad doğrulanır — dizin dışına çıkma denemesi kabul edilmez."""
    if not _TAM_RE.match(name or ""):
        return None
    p = BACKUP_DIR / name
    return p if p.is_file() else None


def tam_yedek_yasi_gun() -> float | None:
    """En son tam yedeğin kaç gün önce alındığı; hiç yoksa None.

    Panel bunu gösteriyor: dışarı indirilmeyen bir yedek, olmayan yedektir —
    bayatladığını GÖRMEK gerekir.
    """
    kayitlar = list_full_backups()
    if not kayitlar:
        return None
    son = datetime.fromisoformat(kayitlar[0]["created_at"])
    return (datetime.now(_TR) - son).total_seconds() / 86400


# ─── DIŞARI KOPYA TAKİBİ ──────────────────────────────────────────────────
# Tam yedeği ALMAK yetmez; sunucu diski ölürse sunucudaki arşiv de gider.
# Önemli olan kendi diskine İNDİRİLMİŞ olması. İndirme ucu başarılı her
# istekte buraya iz bırakır; hatırlatma bu ize bakar.
_INDIRME_IZI = ".son-tam-yedek-indirme"
_HATIRLATMA_IZI = ".son-yedek-hatirlatma"
HATIRLATMA_ESIK_GUN = 30      # "aylık" — Utku'nun seçtiği sıklık
HATIRLATMA_ARALIK_GUN = 7     # eşik aşıldıktan sonra haftada bir, her gün değil


def indirme_kaydet(name: str) -> None:
    """Tam yedek indirildi — zamanı ve dosya adını yaz. Hata akışı bozmaz."""
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        (BACKUP_DIR / _INDIRME_IZI).write_text(
            json.dumps({"ad": name, "zaman": datetime.now(_TR).isoformat()},
                       ensure_ascii=False), encoding="utf-8")
    except OSError as e:
        logger.warning(f"[backup] indirme izi yazılamadı: {e}")


def son_indirme() -> dict | None:
    try:
        veri = json.loads((BACKUP_DIR / _INDIRME_IZI).read_text(encoding="utf-8"))
        veri["zaman"] = datetime.fromisoformat(veri["zaman"])
        return veri
    except (OSError, ValueError, KeyError):
        return None


def disari_kopya_yasi_gun(simdi: datetime | None = None) -> float | None:
    """Son tam yedek İNDİRMESİNİN kaç gün önce yapıldığı; hiç yoksa None."""
    s = son_indirme()
    if not s:
        return None
    return ((simdi or datetime.now(_TR)) - s["zaman"]).total_seconds() / 86400


def hatirlatma_mesaji(simdi: datetime | None = None) -> str | None:
    """Gönderilmesi gereken hatırlatma metni; gerekmiyorsa None.

    Eşik (30 gün) aşılınca HER GÜN değil haftada bir hatırlatır — her sabah
    gelen aynı mesaj bir süre sonra okunmadan geçilir, uyarı işlevini yitirir.
    """
    simdi = simdi or datetime.now(_TR)
    yas = disari_kopya_yasi_gun(simdi)
    if yas is not None and yas < HATIRLATMA_ESIK_GUN:
        return None
    try:
        son_h = datetime.fromisoformat(
            (BACKUP_DIR / _HATIRLATMA_IZI).read_text(encoding="utf-8").strip())
        if (simdi - son_h).total_seconds() / 86400 < HATIRLATMA_ARALIK_GUN:
            return None
    except (OSError, ValueError):
        pass
    if yas is None:
        return ("💾 <b>Tam yedek hiç indirilmedi.</b>\n"
                "Sunucu diski ölürse tasarım dosyaları kalıcı olarak kaybolur. "
                "Panel → Platform → Tam Yedek → al ve kendi diskine indir.")
    return (f"💾 <b>Son tam yedek {int(yas)} gün önce indirildi.</b>\n"
            "Kendi diskindeki kopya eskidi. Panel → Platform → Tam Yedek → "
            "yeni yedek al ve indir.")


def hatirlatma_gonderildi(simdi: datetime | None = None) -> None:
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        (BACKUP_DIR / _HATIRLATMA_IZI).write_text(
            (simdi or datetime.now(_TR)).isoformat(), encoding="utf-8")
    except OSError as e:
        logger.warning(f"[backup] hatırlatma izi yazılamadı: {e}")
