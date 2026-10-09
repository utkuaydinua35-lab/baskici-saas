#!/usr/bin/env python3
"""backend/.env temizliği — davranışı DEĞİŞTİRMEDEN.

2026-10 denetiminde bulunanlar:
  • .env'ye yanlışlıkla yapıştırılmış nginx satırları ("listen 443 ssl;",
    "ssl_certificate ..."). systemd bunları "geçersiz atama" diye atlıyor,
    ama dosyayı okuyan her araç için tuzak.
  • Aynı anahtar iki kez: SESSION_SECRET, RESEND_API_KEY, RESEND_FROM.
    Hem systemd EnvironmentFile hem dotenv SONUNCUYU kullanır; öndeki kopya
    ölü ama "hangisi geçerli" karışıklığı yaratıyor (bir gün biri öndekini
    değiştirip etkisini göremez).

Yapılan: önce zaman damgalı yedek (.env.bak-*), sonra
  - "ANAHTAR=değer" biçiminde olmayan (yorum da olmayan) satırlar silinir,
  - tekrarlanan anahtarların ÖNCEKİ kopyaları silinir (etkin olan, yani
    sonuncusu, kalır → çalışan sistem aynen devam eder).
DEĞERLER EKRANA YAZILMAZ — yalnız anahtar adları.

Kullanım:  python3 deploy/env_temizle.py [yol]   (varsayılan backend/.env)
           --dene  : yalnız rapor, dosyaya dokunma
"""
from __future__ import annotations

import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ANAHTAR = re.compile(r"^\s*(export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")


def main() -> int:
    argumanlar = [a for a in sys.argv[1:] if not a.startswith("--")]
    dene = "--dene" in sys.argv
    yol = Path(argumanlar[0] if argumanlar else Path(__file__).resolve().parent.parent / "backend" / ".env")
    satirlar = yol.read_text().splitlines()

    son_konum: dict[str, int] = {}
    for i, s in enumerate(satirlar):
        m = ANAHTAR.match(s)
        if m:
            son_konum[m.group(2)] = i

    kalan, gecersiz, tekrar = [], [], []
    for i, s in enumerate(satirlar):
        cizgi = s.strip()
        if not cizgi or cizgi.startswith("#"):
            kalan.append(s)
            continue
        m = ANAHTAR.match(s)
        if not m:
            gecersiz.append(i + 1)
            continue
        if son_konum[m.group(2)] != i:
            tekrar.append(m.group(2))
            continue
        kalan.append(s)

    print(f"{yol}: {len(satirlar)} satır")
    print(f"  geçersiz satır (silinecek): {len(gecersiz)} — satır no: {gecersiz or '-'}")
    print(f"  tekrarlanan anahtarın eski kopyası (silinecek): {sorted(set(tekrar)) or '-'}")
    if not gecersiz and not tekrar:
        print("  temiz — değişiklik yok")
        return 0
    if dene:
        print("  --dene: dosyaya dokunulmadı")
        return 0
    yedek = yol.with_name(f".env.bak-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(yol, yedek)
    yol.write_text("\n".join(kalan) + "\n")
    print(f"  TEMİZLENDİ — yedek: {yedek} (geri almak için: cp {yedek} {yol})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
