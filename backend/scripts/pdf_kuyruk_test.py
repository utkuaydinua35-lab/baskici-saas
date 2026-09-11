"""PDF hazırlama kuyruğu — durum/zaman aşımı semantiği ve SÜREÇLER ARASI görünürlük.

Belirti 1: toplu hazırlamada sondaki kalıpların rozeti bitince güncellenmiyordu
(F5 gerekiyordu). Sebep: ZAMAN_ASIMI kuyruğa alınma anından sayılıyordu; işler
SIRAYLA çalıştığı için sondaki iş daha BAŞLAMADAN "yaşı" sınırı geçiyor,
durum() 'yok' dönüyor ve panel o kalıbı izlemeyi bırakıyordu.

Belirti 2 (ikinci worker hazırlığı): iş kaydı süreç BELLEĞİNDEYDİ. Başka bir
worker "yok" görüp aynı 3-4 dakikalık CPU işini ikinci kez başlatırdı. Kayıt
artık dosyada; bu test onu AYRI BİR SÜREÇTEN okuyarak doğrular.

Dosyadaki kaydın bellekten farkı: süreç ölünce SİLİNMEZ. Deploy sonrası
sırada bekleyen iş sonsuza dek "hazırlanıyor" görünmemeli — sahibi ölmüş iş
ölü sayılır; bu da sınanıyor.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

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


def degistir(mid, anahtar, **alanlar):
    """İş kaydını yapay olarak değiştir (başka süreçteki iş gibi davransın)."""
    yol = job._is_yolu(mid, anahtar)
    with job._surecler_arasi_kilit():
        kayit = job._is_oku(yol) or {}
        kayit.update(alanlar)
        job._is_yaz(yol, kayit)


def baska_surecten(kod: str) -> str:
    """Kodu AYRI bir Python sürecinde çalıştır — ikinci worker'ın gözü."""
    r = subprocess.run(
        [sys.executable, "-c",
         f"import sys; sys.path.insert(0, {str(KOK)!r}); "
         f"from app.services import mold_pdf_job as job; import uuid; {kod}"],
        capture_output=True, text=True, cwd=str(KOK))
    return (r.stdout or "").strip().splitlines()[-1] if r.stdout.strip() else f"HATA: {r.stderr[-300:]}"


def olu_pid() -> int:
    """Şu an yaşamayan bir süreç kimliği."""
    pid = 999_999
    while job._surec_yasiyor(pid):
        pid -= 1
    return pid


mid = uuid.uuid4()
anahtar = f"test{uuid.uuid4().hex[:8]}"
anahtar2 = f"test{uuid.uuid4().hex[:8]}"
arka = SahteArkaPlan()

try:
    print("\n── Kuyruğa alınan iş ──")
    es("baslat True doner", True, job.baslat(arka, mid, anahtar, [], {}))
    d = job.durum(mid, anahtar)
    es("durum hazirlaniyor", "hazirlaniyor", d["durum"])
    es("henuz BASLAMADI", False, d["basladi"])
    es("kuyrukta gorunuyor", True, any(i["anahtar"] == anahtar for i in job.kuyruk()))
    es("ayni is tekrar kuyruga girmez", False, job.baslat(arka, mid, anahtar, [], {}))
    es("kayit DOSYADA", True, job._is_yolu(mid, anahtar).exists())

    print("\n── BAŞKA SÜREÇ (ikinci worker) aynı işi görüyor ──")
    es("başka süreç: durum hazirlaniyor", "hazirlaniyor",
       baska_surecten(f"print(job.durum(uuid.UUID({str(mid)!r}), {anahtar!r})['durum'])"))
    es("başka süreç: kuyrukta var", "True",
       baska_surecten(f"print(any(i['anahtar']=={anahtar!r} for i in job.kuyruk()))"))
    es("başka süreç AYNI işi İKİNCİ KEZ başlatamaz", "False",
       baska_surecten("class A:\n    def add_task(self,*a,**k): pass\n"
                      if False else
                      f"print(job.baslat(type('A',(),{{'add_task':lambda s,*a,**k:None}})(), "
                      f"uuid.UUID({str(mid)!r}), {anahtar!r}, [], {{}}))"))

    print("\n── Sırada bekleyen iş ZAMAN AŞIMINA uğramamalı ──")
    # Başlangıç saati eski ama iş henüz başlamadı ve kuyruğa yakın zamanda alındı.
    degistir(mid, anahtar, baslangic=time.time() - (job.ZAMAN_ASIMI + 600))
    es("hala hazirlaniyor (yok DEGIL)", "hazirlaniyor", job.durum(mid, anahtar)["durum"])
    es("kuyrukta hala var", True, any(i["anahtar"] == anahtar for i in job.kuyruk()))

    print("\n── ...ama SONSUZA DEK de beklemez ──")
    degistir(mid, anahtar, kuyruga_alindi=time.time() - (2 * job.ZAMAN_ASIMI + 60))
    es("kuyrukta çok uzun kalan iş ölü sayılır", "yok", job.durum(mid, anahtar)["durum"])
    degistir(mid, anahtar, kuyruga_alindi=time.time())

    print("\n── ÇALIŞAN iş zaman aşımına uğrar ──")
    degistir(mid, anahtar, basladi=True, baslangic=time.time() - (job.ZAMAN_ASIMI + 60))
    es("calisan + eski -> yok", "yok", job.durum(mid, anahtar)["durum"])
    es("kuyruktan dustu", False, any(i["anahtar"] == anahtar for i in job.kuyruk()))
    es("takilan is yeniden kuyruga alinabilir", True, job.baslat(arka, mid, anahtar, [], {}))

    print("\n── SAHİBİ ÖLMÜŞ iş (deploy/yeniden başlatma) ──")
    # Bellekteki kayıt süreçle ölürdü; dosyadaki ölmez. Ölü sürecin işi
    # "hazırlanıyor" görünmeye devam ederse PDF hiç üretilmezdi.
    degistir(mid, anahtar, basladi=False, pid=olu_pid(),
             baslangic=time.time(), kuyruga_alindi=time.time())
    es("ölü sürecin işi 'yok'", "yok", job.durum(mid, anahtar)["durum"])
    es("ölü sürecin işi kuyrukta görünmez", False,
       any(i["anahtar"] == anahtar for i in job.kuyruk()))
    es("yeniden başlatılabilir", True, job.baslat(arka, mid, anahtar, [], {}))

    print("\n── Çalışmaya başlayınca saat SIFIRLANIR ──")
    job.baslat(arka, mid, anahtar2, [], {})
    degistir(mid, anahtar2, baslangic=time.time() - 900)   # 15 dk kuyrukta bekledi
    fn, a, k = arka.gorevler[-1]
    try:
        fn(*a, **k)          # _uret — şablon yok, hata ile bitecek
    except Exception:  # noqa: BLE001
        pass
    kayit = job._is_oku(job._is_yolu(mid, anahtar2))
    es("is 'basladi' isaretlendi ya da hata yazildi", True,
       kayit is None or kayit.get("durum") == "hata" or kayit.get("basladi") is True)
    es("hata kaydı durum()'da görünüyor", "hata", job.durum(mid, anahtar2)["durum"])

    print("\n── Zombi süreç 'yaşıyor' sayılmaz ──")
    # Bitmiş ama toplanmamış süreç kill(0)'a "yaşıyor" der; iş 20 dk
    # "hazırlanıyor" görünür, PDF hiç tekrar denenemezdi.
    zombi = subprocess.Popen([sys.executable, "-c", "pass"])
    time.sleep(1.0)                      # bitsin ama wait() ÇAĞRILMASIN
    es("bitmiş çocuk süreç ölü sayılır", False, job._surec_yasiyor(zombi.pid))
    es("yaşayan süreç (kendimiz) yaşıyor sayılır", True, job._surec_yasiyor(os.getpid()))

    print("\n── ÜRETİMDEKİ HATA: çizim sırasında worker ÖLDÜRÜLÜR ──")
    # uvicorn --workers 2: ebeveyn süreç 5 sn'de bir worker'a "yaşıyor musun"
    # diye soruyor; PyMuPDF kilidi (GIL) bırakmadığı için cevap gelmiyor ve
    # worker öldürülüyordu. Çizim worker'ın İÇİNDEYSE PDF ölür, durum "yok"a
    # döner ve her tıklama baştan başlar. Çizim AYRI süreçteyse worker'ın
    # ölümü üretimi durdurmamalı.
    anahtar3 = f"test{uuid.uuid4().hex[:8]}"
    job.baslat(SahteArkaPlan(), mid, anahtar3, [], {})
    ortam = {**os.environ, "KALIP_PDF_TEST_GECIKME_SN": "4"}
    worker = subprocess.Popen(
        [sys.executable, "-c",
         f"import sys; sys.path.insert(0, {str(KOK)!r}); import uuid; "
         f"from app.services import mold_pdf_job as job; "
         f"job._uret(uuid.UUID({str(mid)!r}), {anahtar3!r}, [], {{}})"],
        cwd=str(KOK), env=ortam)
    cocuk_pid = None
    son = time.time() + 15
    while time.time() < son:
        k = job._is_oku(job._is_yolu(mid, anahtar3)) or {}
        if k.get("basladi") and k.get("pid") not in (None, worker.pid):
            cocuk_pid = k["pid"]
            break
        time.sleep(0.1)
    es("çizimi worker DEĞİL ayrı bir süreç yapıyor", True, cocuk_pid is not None)
    es("çocuk worker'ın oturumunda değil (sinyali ona geçmez)", True,
       cocuk_pid is not None and os.getsid(cocuk_pid) != os.getsid(worker.pid))
    worker.kill()                        # sağlık kontrolünün yaptığı
    worker.wait()
    es("worker ölünce iş HÂLÂ sürüyor", "hazirlaniyor", job.durum(mid, anahtar3)["durum"])
    son = time.time() + 30
    while time.time() < son and job.durum(mid, anahtar3)["durum"] == "hazirlaniyor":
        time.sleep(0.3)
    # Şablon boş olduğu için çizim hata ile biter — önemli olan, worker öldükten
    # SONRA çocuğun işi bitirip sonucu yazması ("yok"a düşmemesi).
    es("çocuk işi bitirip sonucu yazdı ('yok' değil)", "hata", job.durum(mid, anahtar3)["durum"])
    es("girdi dosyası temizlendi", False, job._girdi_yolu(mid, anahtar3).exists())

    print("\n── Çocuk hata YAZAMADAN ölürse sebep görünür ──")
    anahtar4 = f"test{uuid.uuid4().hex[:8]}"
    job.baslat(SahteArkaPlan(), mid, anahtar4, [], {})
    ortam = {**os.environ, "KALIP_PDF_TEST_GECIKME_SN": "30"}
    worker = subprocess.Popen(
        [sys.executable, "-c",
         f"import sys; sys.path.insert(0, {str(KOK)!r}); import uuid; "
         f"from app.services import mold_pdf_job as job; "
         f"job._uret(uuid.UUID({str(mid)!r}), {anahtar4!r}, [], {{}})"],
        cwd=str(KOK), env=ortam)
    cocuk_pid = None
    son = time.time() + 15
    while time.time() < son:
        k = job._is_oku(job._is_yolu(mid, anahtar4)) or {}
        if k.get("basladi") and k.get("pid") not in (None, worker.pid):
            cocuk_pid = k["pid"]
            break
        time.sleep(0.1)
    os.kill(cocuk_pid, 9)                # bellek yetmedi / dışarıdan öldürüldü
    worker.wait(timeout=15)
    d = job.durum(mid, anahtar4)
    es("sessizce 'yok'a düşmek yerine hata", "hata", d["durum"])
    es("mesaj yeniden denemeyi söylüyor", True, "tekrar deneyin" in (d.get("mesaj") or ""))

    print("\n── Kalıp değişince iş kayıtları da silinir ──")
    job.gecersiz_kil(mid)
    es(".is dosyaları silindi", [], sorted(p.name for p in job._dizin().glob(f"{mid}_*")))
    es("durum artık yok", "yok", job.durum(mid, anahtar)["durum"])
finally:
    for p in job._dizin().glob(f"{mid}_*"):
        p.unlink(missing_ok=True)

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
