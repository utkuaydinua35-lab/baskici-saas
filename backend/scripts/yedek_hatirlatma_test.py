"""Tam yedek hatırlatması — "indirilmedi" durumunu yakalıyor ve spam yapmıyor mu?

⚠ NEDEN: panel uyarısı yalnız Platform sayfası açılınca görünüyordu. Ayrıca
bayatlık yedeğin ALINMASINA göre ölçülüyordu; oysa sunucu diski ölürse
sunucudaki arşiv de gider — önemli olan kendi diske İNDİRİLMİŞ olması.

Veritabanı gerektirmez: geçici bir yedek dizininde çalışır.
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import backup  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


_gercek_dizin = backup.BACKUP_DIR
backup.BACKUP_DIR = Path(tempfile.mkdtemp())
try:
    simdi = backup.datetime.now(backup._TR)

    print("\n── hiç indirilmemiş ──")
    m = backup.hatirlatma_mesaji(simdi)
    es("hatırlatma çıkıyor", True, bool(m))
    es("'hiç indirilmedi' diyor", True, "hiç indirilmedi" in (m or ""))

    print("\n── haftada bir, her gün değil ──")
    backup.hatirlatma_gonderildi(simdi)
    es("aynı gün tekrar YOK", None, backup.hatirlatma_mesaji(simdi + timedelta(hours=5)))
    es("6 gün sonra hâlâ YOK", None, backup.hatirlatma_mesaji(simdi + timedelta(days=6)))
    es("7 gün sonra yeniden var", True, bool(backup.hatirlatma_mesaji(simdi + timedelta(days=7))))

    print("\n── yeni indirilmiş ──")
    (backup.BACKUP_DIR / backup._HATIRLATMA_IZI).unlink()
    backup.indirme_kaydet("tam-yedek-20260101-000000.tar")
    es("indirme izi okunuyor", "tam-yedek-20260101-000000.tar", (backup.son_indirme() or {}).get("ad"))
    es("taze indirmede hatırlatma YOK", None, backup.hatirlatma_mesaji())

    print("\n── 31 gün önce indirilmiş ──")
    eski = simdi - timedelta(days=31)
    (backup.BACKUP_DIR / backup._INDIRME_IZI).write_text(
        json.dumps({"ad": "x.tar", "zaman": eski.isoformat()}), encoding="utf-8")
    m = backup.hatirlatma_mesaji(simdi)
    es("eşik aşıldı → hatırlatma", True, bool(m))
    es("kaç gün olduğunu söylüyor", True, "31 gün" in (m or ""))
    es("29 günde hatırlatma YOK", None,
       backup.hatirlatma_mesaji(eski + timedelta(days=29)))

    print("\n── bozuk iz dosyası akışı bozmaz ──")
    (backup.BACKUP_DIR / backup._INDIRME_IZI).write_text("bozuk{", encoding="utf-8")
    es("bozuk iz → 'indirilmemiş' sayılır", None, backup.disari_kopya_yasi_gun())

    print("\n── indirme ucu izi GERÇEKTEN yazıyor ──")
    from fastapi.testclient import TestClient

    from app.main import app
    from app.routers.platform import _jeton_serici

    ad = "tam-yedek-20260102-030000.tar"
    (backup.BACKUP_DIR / ad).write_bytes(b"sahte arsiv")
    (backup.BACKUP_DIR / backup._INDIRME_IZI).unlink()
    r = TestClient(app).get(f"/api/platform/tam-yedek/{ad}/download?jeton={_jeton_serici().dumps({'ad': ad})}")
    es("indirme 200", 200, r.status_code)
    es("iz bu dosyayı gösteriyor", ad, (backup.son_indirme() or {}).get("ad"))
    es("jetonsuz indirme iz YAZMAZ", 403,
       TestClient(app).get(f"/api/platform/tam-yedek/{ad}/download").status_code)
finally:
    backup.BACKUP_DIR = _gercek_dizin

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
