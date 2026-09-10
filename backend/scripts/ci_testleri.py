"""CI'da koşan test paketleri — VERİTABANI GEREKTİRMEYENLER.

NE İŞE YARAR: her `git push` sonrası GitHub bu dosyayı çalıştırır. Bir şey
kırıldıysa e-posta gelir ve commit'in yanında kırmızı bir işaret çıkar. Yani
"bozdum ama fark etmedim" durumu ortadan kalkar.

⚠ NEDEN BU DOSYA VAR: 44 test paketi elle çalıştırılıyordu ve her seferinde
bir alt kümesi seçiliyordu. 2026-09-11'de tam olarak bu yüzden bir paket
(surat_dogrudan_test) günlerce KIRIK kaldı: barkod düzeltmesinde bir fonksiyon
iki değer dönmeye başladı, uygulama kodundaki çağıranlar güncellendi ama test
scriptleri taranmadı ve o paket o gün hiç koşulmadı.

SEÇİM OTOMATİK: `SessionLocal` geçmeyen her paket alınır. Yeni bir test yazınca
listeye eklemek GEREKMEZ.

⚠ Ölçüt kusursuz değil: `SessionLocal` kullanmadan TestClient ile uca istek
atan bir test de veritabanına gider (uygulama üzerinden). Bu tür paketler ATLA
sözlüğüne sebebiyle yazılır. CI'a Postgres servisi eklenince o satırlar silinir
ve paketler kendiliğinden geri döner.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent

# Otomatik seçime rağmen ATLANANLAR — her satır SEBEP yazmalı.
ATLA: dict[str, str] = {
    # `SessionLocal` içermiyor ama TestClient ile /api/auth/login çağırıyor,
    # yani uygulama üzerinden veritabanına gidiyor. Geliştirici makinesinde
    # DB açık olduğu için geçiyor, CI'da düşerdi.
    # CI'a Postgres servisi eklenince bu satır SİLİNMELİ.
    "native_kabuk_test.py": "TestClient ile giriş yapıyor → DB gerekiyor",
    # pg_dump/psql ile GERÇEK yedek alıp geçici bir veritabanı açıp kapatıyor.
    # CI'da ne veri var ne de anlamı; elle/ayda bir koşulur.
    "yedek_provasi_test.py": "gerçek veritabanı + pg_dump gerektiriyor (elle koşulur)",
}


def _db_gerekir(yol: Path) -> bool:
    return "SessionLocal" in yol.read_text(encoding="utf-8")


def main() -> int:
    paketler = sorted(p for p in KOK.glob("*_test.py") if not _db_gerekir(p))
    kosulan, dusen, atlanan = [], [], []

    for p in paketler:
        if p.name in ATLA:
            atlanan.append((p.name, ATLA[p.name]))
            continue
        r = subprocess.run([sys.executable, str(p)], capture_output=True, text=True)
        son = [x for x in (r.stdout or "").strip().split("\n") if x.strip()]
        ozet = next((x.strip() for x in reversed(son) if "GECTI" in x or "geçti" in x), "")
        if r.returncode == 0:
            kosulan.append((p.name, ozet))
            print(f"  ✓ {p.name:<32} {ozet}")
        else:
            dusen.append((p.name, r))
            print(f"  ✗ {p.name:<32} {ozet or 'ÇÖKTÜ'}")

    for ad, sebep in atlanan:
        print(f"  · {ad:<32} atlandı — {sebep}")

    if dusen:
        print("\n" + "=" * 60)
        for ad, r in dusen:
            print(f"\n──── {ad} ────")
            print((r.stdout or "")[-2500:])
            if r.stderr:
                print("STDERR:", (r.stderr or "")[-1500:])

    print("\n" + "=" * 60)
    print(f"paket: {len(kosulan)} geçti, {len(dusen)} düştü, {len(atlanan)} atlandı")
    return 1 if dusen else 0


if __name__ == "__main__":
    sys.exit(main())
