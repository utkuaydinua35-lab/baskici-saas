"""YEDEK PROVASI — alınan yedek GERÇEKTEN geri yüklenebiliyor mu?

⚠ DENENMEMİŞ YEDEK, YEDEK DEĞİLDİR. Bu betik tam yedeği üretip BOŞ bir
veritabanına geri yükler ve satır sayılarını canlıyla karşılaştırır. pg_dump'ın
sessizce eksik/bozuk döküm üretmesi (sürüm uyuşmazlığı, izin, kesilmiş çıktı)
ancak böyle yakalanır.

Ayrıca arşivin kendi kendine yeter olduğunu sınar: geri yükleme betiği, okunur
açıklama ve doğrulama özeti İÇİNDE mi.

⚠ 'yedek_provasi' adında geçici bir veritabanı açar ve SONUNDA SİLER. Canlı
veritabanına DOKUNMAZ (yalnız okur).

Elle koşulur:  .venv/bin/python scripts/yedek_provasi_test.py
Önerilen sıklık: ayda bir.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.services import backup  # noqa: E402

GECTI = KALDI = 0
PROVA_DB = "yedek_provasi"


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


sa_url = get_settings().database_url
ana = sa_url.rsplit("/", 1)[0]
prova_sa = f"{ana}/{PROVA_DB}"
prova_pg = prova_sa.replace("+psycopg", "").replace("+psycopg2", "")
adm = create_engine(f"{ana}/postgres", isolation_level="AUTOCOMMIT")

print("\n── tam yedek üretiliyor ──")
_t0 = time.time()
sonuc = backup.run_full_backup()
_sure = time.time() - _t0
ars = backup.BACKUP_DIR / sonuc["name"]
print(f"  · {sonuc['name']} · {sonuc['size'] / 1024 / 1024:.1f} MB · {_sure:.1f} sn")
es("arşiv oluştu", True, ars.is_file())
es("sha256 üretildi", 64, len(sonuc.get("sha256") or ""))

print("\n── arşiv KENDİ KENDİNE YETİYOR mu ──")
# Felaket anında elinde yalnız bu dosya olacak: ne yapacağını İÇİNDEN
# okuyabilmeli, dışarıdan bir betiğe muhtaç olmamalı.
_liste = subprocess.run(["tar", "-tf", str(ars)], capture_output=True, text=True).stdout.split("\n")
for gerekli in ("veritabani.sql.gz", "MANIFEST.json", "BENIOKU.txt", "GERI-YUKLE.sh"):
    es(f"içinde {gerekli}", True, gerekli in _liste)
es("bilgi dosyaları arşivin BAŞINDA (6 GB açmadan okunur)", True,
   _liste.index("MANIFEST.json") < 5)
es("cache/ DIŞLANDI (yeniden üretilebilir)", 0,
   sum(1 for x in _liste if "/cache/" in x))

_gec = tempfile.mkdtemp()
subprocess.run(["tar", "-xf", str(ars), "-C", _gec,
                "veritabani.sql.gz", "MANIFEST.json", "GERI-YUKLE.sh"], check=True)
_man = json.loads((pathlib.Path(_gec) / "MANIFEST.json").read_text(encoding="utf-8"))
es("manifest sürümlü", 1, _man.get("surum"))
es("manifest dosya sayısı gerçekçi", True, (_man.get("storage_dosya_sayisi") or 0) > 0)
_betik = (pathlib.Path(_gec) / "GERI-YUKLE.sh").read_text(encoding="utf-8")
es("geri yükleme betiği ONAY istiyor", True, "--onayliyorum" in _betik)
es("betik sözdizimi geçerli", 0,
   subprocess.run(["bash", "-n", str(pathlib.Path(_gec) / "GERI-YUKLE.sh")]).returncode)

print("\n── indirme ucu: yalnız imzalı jetonla ──")
# ⚠ Bu dosya SİSTEMİN TAMAMI (şifre özetleri, müşteri adresleri, tasarımlar).
# İndirme bağlantısı sızarsa her şey sızar; jeton kısa ömürlü ve TEK DOSYAYA
# bağlı olmalı.
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.routers.platform import _jeton_serici  # noqa: E402

_C = TestClient(app)
_yol = f"/api/platform/tam-yedek/{sonuc['name']}/download"
es("jetonsuz reddedilir", 403, _C.get(_yol).status_code)
es("uydurma jeton reddedilir", 403, _C.get(f"{_yol}?jeton=abc").status_code)
_baska = _jeton_serici().dumps({"ad": "tam-yedek-19990101-000000.tar"})
es("BAŞKA dosyanın jetonu reddedilir", 403, _C.get(f"{_yol}?jeton={_baska}").status_code)
_gecerli = _jeton_serici().dumps({"ad": sonuc["name"]})
_r = _C.get(f"{_yol}?jeton={_gecerli}")
es("geçerli jetonla iner", 200, _r.status_code)
es("inen boyut arşivle aynı", sonuc["size"], len(_r.content))
es("jeton üretme ucu yetki istiyor", 401,
   _C.post(f"/api/platform/tam-yedek/{sonuc['name']}/indirme-jetonu").status_code)
es("liste ucu yetki istiyor", 401, _C.get("/api/platform/tam-yedek").status_code)

print("\n── BOŞ veritabanına GERİ YÜKLE ──")
with adm.connect() as c:
    c.execute(text(f"drop database if exists {PROVA_DB}"))
    c.execute(text(f"create database {PROVA_DB}"))
try:
    _sql = os.path.join(_gec, "veritabani.sql.gz")
    _t0 = time.time()
    p1 = subprocess.Popen(["gunzip", "-c", _sql], stdout=subprocess.PIPE)
    p2 = subprocess.run(["psql", "-q", "-v", "ON_ERROR_STOP=1", prova_pg],
                        stdin=p1.stdout, capture_output=True, text=True)
    p1.stdout.close(); p1.wait()
    es("psql hatasız bitti", 0, p2.returncode)
    if p2.returncode:
        print("      ", (p2.stderr or "")[-500:])
    print(f"  · yükleme süresi {time.time() - _t0:.1f} sn")

    print("\n── satır sayıları CANLIYLA aynı mı ──")
    tablolar = ["orders", "line_items", "molds", "mold_items", "designs",
                "users", "stores", "customers", "order_status_history"]
    canli = create_engine(sa_url)
    geri = create_engine(prova_sa)
    with canli.connect() as c1, geri.connect() as c2:
        for t in tablolar:
            a = c1.execute(text(f"select count(*) from {t}")).scalar()
            b = c2.execute(text(f"select count(*) from {t}")).scalar()
            es(f"{t} ({a})", a, b)
    canli.dispose(); geri.dispose()
finally:
    with adm.connect() as c:
        c.execute(text(f"drop database if exists {PROVA_DB}"))
    print("\n  · prova veritabanı silindi (canlıya dokunulmadı)")

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
