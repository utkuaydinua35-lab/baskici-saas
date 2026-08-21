"""Mevcut tasarımların kalıp rasterini ÖNCEDEN üret — bir kerelik ısıtma.

Kalıp PDF'i her tasarımı bir kez çizmek zorunda (ölçümde 6-19 sn). Bu maliyet
önbelleğe alınıyor ama ilk kalıp yine bekliyor. Bu betik tüm tasarımların
rasterini önden üretir; sonrasında kalıp PDF'leri hazır rasteri gömer.

Uzun sürer (tasarım başına ~10 sn). tmux içinde çalıştır:
    cd ~/baskici-saas/backend && .venv/bin/python scripts/tasarim_raster_isit.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Design  # noqa: E402
from app.services import mold_pdf as MP  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        tasarimlar = [
            d for d in db.scalars(select(Design).order_by(Design.created_at.desc())).all()
            if d.file_path and (d.file_format or "").lower() == "pdf"
        ]
    finally:
        db.close()

    print(f"{len(tasarimlar)} PDF tasarım taranacak "
          f"(eşik {MP.RASTER_ESIK_MB} MB üstü rasterlenir)\n")
    uretildi = atlandi = hata = 0
    basla = time.time()
    for i, d in enumerate(tasarimlar, 1):
        p = MP._abs_path(d.file_path)
        if not p.exists():
            atlandi += 1
            continue
        mb = p.stat().st_size / 1024 / 1024
        if mb <= MP.RASTER_ESIK_MB:
            atlandi += 1
            continue
        # zaten varsa hızlı geçer
        t = time.time()
        ok = MP.onbellek_hazirla(d.file_path)
        sure = time.time() - t
        if ok:
            uretildi += 1
        else:
            hata += 1
        if i % 10 == 0 or sure > 5:
            gecen = time.time() - basla
            kalan = (gecen / i) * (len(tasarimlar) - i)
            print(f"  [{i}/{len(tasarimlar)}] {str(d.code)[:14]:<16} {mb:5.1f}MB"
                  f" {sure:5.1f}sn · geçen {gecen/60:4.1f}dk · tahmini kalan {kalan/60:4.1f}dk")

    print(f"\nüretilen {uretildi} · atlanan {atlandi} · hata {hata}"
          f" · toplam {(time.time()-basla)/60:.1f} dk")
    onb = MP.STORAGE_ROOT / "cache" / "tasarim_raster"
    if onb.exists():
        n = sum(1 for _ in onb.iterdir())
        mb = sum(f.stat().st_size for f in onb.iterdir()) / 1024 / 1024
        print(f"önbellek: {n} dosya · {mb:.0f} MB · {onb}")


if __name__ == "__main__":
    main()
