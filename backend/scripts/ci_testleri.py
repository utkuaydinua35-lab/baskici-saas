"""CI'da koşan test paketleri — HEPSİ (veritabanı CI'da kuruluyor).

NE İŞE YARAR: her `git push` sonrası GitHub bu dosyayı çalıştırır. Bir şey
kırıldıysa commit'in yanında kırmızı bir işaret çıkar ve e-posta gelir. Yani
"bozdum ama fark etmedim" durumu ortadan kalkar.

⚠ NEDEN VAR: 47 test paketi elle çalıştırılıyordu ve her seferinde bir alt
kümesi seçiliyordu. 2026-09-11'de tam bu yüzden surat_dogrudan_test günlerce
KIRIK kaldı: barkod düzeltmesinde bir fonksiyon iki değer dönmeye başladı,
uygulama kodundaki çağıranlar güncellendi ama test scriptleri taranmadı ve o
paket o gün hiç koşulmadı.

CI'da boş bir Postgres kurulup göçler çalıştırılıyor ve `ci_tohum.py` asgari
veriyi yazıyor. Tohum ŞART: paketlerin çoğu veri bulamayınca "atlandı" deyip
ÇIKIŞ KODU 0 ile biter — CI yemyeşil olur ama hiçbir şey sınanmamış olur.

Yeni bir test yazınca listeye eklemek GEREKMEZ; `scripts/*_test.py` deseni
otomatik toplanır.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent

# CI'da KOŞULMAYANLAR — her satır SEBEP yazmalı.
ATLA: dict[str, str] = {
    # pg_dump/psql ile gerçek yedek alıp geçici veritabanı açıp kapatıyor;
    # CI'da anlamı yok. Ayda bir ELLE koşulur (yedek provası).
    "yedek_provasi_test.py": "gerçek yedek + geçici veritabanı — elle koşulur",
    # Vitrin sepet/kupon akışı mağaza ayarları (kargo, ödeme) istiyor;
    # tohumda henüz yok. 22/26 geçiyor, kalan 4'ü ayar bekliyor.
    "smoke_test.py": "vitrin mağaza ayarları tohumda yok (bkz. ci_tohum.py)",
}


def main() -> int:
    paketler = sorted(KOK.glob("*_test.py"))
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
