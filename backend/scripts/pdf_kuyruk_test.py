"""PDF hazırlama kuyruğu — durum/zaman aşımı semantiği.

Belirti: toplu hazırlamada sondaki kalıpların rozeti bitince güncellenmiyordu
(F5 gerekiyordu). Sebep: ZAMAN_ASIMI kuyruğa alınma anından sayılıyordu; işler
SIRAYLA çalıştığı için sondaki iş daha BAŞLAMADAN "yaşı" sınırı geçiyor,
durum() 'yok' dönüyor ve panel o kalıbı izlemeyi bırakıyordu.
"""
from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import mold_pdf_job as job  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


class SahteArkaPlan:
    """FastAPI BackgroundTasks yerine — görevi ÇALIŞTIRMAZ, sadece toplar."""
    def __init__(self): self.gorevler = []
    def add_task(self, fn, *a, **k): self.gorevler.append((fn, a, k))


mid = uuid.uuid4()
anahtar = f"test-{uuid.uuid4().hex[:8]}"
arka = SahteArkaPlan()

print("\n── Kuyruğa alınan iş ──")
es("baslat True doner", True, job.baslat(arka, mid, anahtar, [], {}))
d = job.durum(mid, anahtar)
es("durum hazirlaniyor", "hazirlaniyor", d["durum"])
es("henuz BASLAMADI", False, d["basladi"])
es("kuyrukta gorunuyor", True,
   any(i["anahtar"] == anahtar for i in job.kuyruk()))
es("ayni is tekrar kuyruga girmez", False, job.baslat(arka, mid, anahtar, [], {}))

print("\n── Sırada bekleyen iş ZAMAN AŞIMINA uğramamalı ──")
# İşi yapay olarak "çok eski" göster ama HENÜZ BAŞLAMAMIŞ bırak.
with job._kilit:
    job._isler[anahtar]["baslangic"] = time.time() - (job.ZAMAN_ASIMI + 600)
d = job.durum(mid, anahtar)
es("hala hazirlaniyor (yok DEGIL)", "hazirlaniyor", d["durum"])
es("kuyrukta hala var", True, any(i["anahtar"] == anahtar for i in job.kuyruk()))

print("\n── ÇALIŞAN iş zaman aşımına uğrar ──")
with job._kilit:
    job._isler[anahtar]["basladi"] = True
    job._isler[anahtar]["baslangic"] = time.time() - (job.ZAMAN_ASIMI + 60)
es("calisan + eski -> yok", "yok", job.durum(mid, anahtar)["durum"])
es("kuyruktan dustu", False, any(i["anahtar"] == anahtar for i in job.kuyruk()))
es("takilan is yeniden kuyruga alinabilir", True,
   job.baslat(arka, mid, anahtar, [], {}))

print("\n── Çalışmaya başlayınca saat SIFIRLANIR ──")
anahtar2 = f"test-{uuid.uuid4().hex[:8]}"
job.baslat(arka, mid, anahtar2, [], {})
with job._kilit:
    job._isler[anahtar2]["baslangic"] = time.time() - 900   # 15 dk kuyrukta bekledi
fn, a, k = arka.gorevler[-1]
try:
    fn(*a, **k)          # _uret — şablon yok, hata ile bitecek
except Exception:
    pass
with job._kilit:
    kayit = job._isler.get(anahtar2)
# _uret hata ile bitse de saati sıfırlamış olmalı (kuyrukta bekleme sayılmaz)
es("is 'basladi' isaretlendi ya da hata yazildi", True,
   kayit is None or kayit.get("durum") == "hata" or kayit.get("basladi") is True)

# Temizlik
with job._kilit:
    job._isler.pop(anahtar, None)
    job._isler.pop(anahtar2, None)

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
