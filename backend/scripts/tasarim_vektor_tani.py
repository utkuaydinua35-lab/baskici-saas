"""Tasarımlar ne zaman saf vektöre döndü — aya göre kırılım. DEĞİŞTİRMEZ.

7 Ağustos'taki "vektörel + CMYK PDF çıktı" değişikliğinden sonra müşteri
PDF/SVG'leri baskı dosyasına vektör olarak gömülüyor (raster görsel sayısı 0).
Kalıp PDF'i bu dosyaları show_pdf_page ile kopyaladığı için yavaşlıyor.

    cd ~/baskici-saas/backend && .venv/bin/python scripts/tasarim_vektor_tani.py
"""
from __future__ import annotations

import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fitz  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Design  # noqa: E402
from app.services.storage import STORAGE_ROOT  # noqa: E402

ORNEK = 6          # ay başına en fazla kaç dosya açılsın
W_PT, H_PT = 7.9 / 2.54 * 72, 17.0 / 2.54 * 72


def main() -> None:
    db = SessionLocal()
    try:
        aylar = defaultdict(list)
        for d in db.scalars(select(Design).order_by(Design.created_at)).all():
            if not d.file_path or (d.file_format or "").lower() != "pdf":
                continue
            p = STORAGE_ROOT / d.file_path
            if p.exists():
                aylar[str(d.created_at)[:7]].append(p)

        print(f"{'ay':<9} {'pdf':>5} {'ortalama MB':>12} {'gorselli':>10}"
              f" {'orneklem':>9} {'ort. sure':>10}")
        print("─" * 62)
        for ay in sorted(aylar):
            dosyalar = aylar[ay]
            mb = sum(f.stat().st_size for f in dosyalar) / len(dosyalar) / 1024 / 1024
            ornek = dosyalar[:: max(1, len(dosyalar) // ORNEK)][:ORNEK]
            gorselli = 0
            toplam_sure = 0.0
            for f in ornek:
                try:
                    src = fitz.open(str(f))
                    if src.page_count and src[0].get_images(full=False):
                        gorselli += 1
                    src.close()
                except Exception:  # noqa: BLE001
                    continue
                tmp = fitz.open()
                pg = tmp.new_page(width=W_PT, height=H_PT)
                src = fitz.open(str(f))
                t = time.time()
                try:
                    pg.show_pdf_page(pg.rect, src, 0, keep_proportion=False)
                except Exception:  # noqa: BLE001
                    pass
                toplam_sure += time.time() - t
                src.close(); tmp.close()
            oran = f"{gorselli}/{len(ornek)}"
            ort = toplam_sure / max(1, len(ornek))
            isaret = "  ← YAVAŞ" if ort > 2 else ""
            print(f"{ay:<9} {len(dosyalar):>5} {mb:>11.1f}M {oran:>10}"
                  f" {len(ornek):>9} {ort:>9.2f}s{isaret}")

        print("\n'gorselli' = orneklemde icinde gomulu raster GORSEL olan PDF sayisi.")
        print("Bu oran dusup sure yukseliyorsa kirilma noktasi orasidir.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
