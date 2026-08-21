"""Tasarım dosyaları nereye gitti — diskteki gerçek duruma bak. DEĞİŞTİRMEZ.

    cd ~/baskici-saas/backend && .venv/bin/python scripts/kayip_tasarim_tani.py
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Design  # noqa: E402
from app.services.storage import STORAGE_ROOT  # noqa: E402


def main() -> None:
    print(f"STORAGE_ROOT : {STORAGE_ROOT}")
    print(f"  var mi     : {STORAGE_ROOT.exists()}\n")

    db = SessionLocal()
    try:
        tum = db.scalars(select(Design)).all()
        var, yok = [], []
        for d in tum:
            if not d.file_path:
                continue
            (var if (STORAGE_ROOT / d.file_path).exists() else yok).append(d)

        print(f"tasarım: {len(tum)} · dosyası var {len(var)} · YOK {len(yok)}\n")

        # Kayıplar hangi klasörlerde toplanıyor
        print("── Kayıp dosyaların klasörleri ──")
        for klasor, adet in Counter(
                str(Path(d.file_path).parent) for d in yok).most_common(8):
            p = STORAGE_ROOT / klasor
            icerik = len(list(p.iterdir())) if p.exists() else None
            durum = f"klasör VAR, içinde {icerik} dosya" if p.exists() else "klasör YOK"
            print(f"  {adet:>4} kayıp · {klasor[:58]}")
            print(f"        -> {durum}")

        print("\n── Dosyası OLAN tasarımların klasörleri ──")
        for klasor, adet in Counter(
                str(Path(d.file_path).parent) for d in var).most_common(5):
            print(f"  {adet:>4} var   · {klasor[:58]}")

        print("\n── Tarih dağılımı ──")
        def ay(d):
            return str(d.created_at)[:7] if d.created_at else "?"
        vc, yc = Counter(ay(d) for d in var), Counter(ay(d) for d in yok)
        for a in sorted(set(vc) | set(yc)):
            print(f"  {a}:  var {vc.get(a,0):>4}   kayıp {yc.get(a,0):>4}")

        print("\n── Diskte gerçekten ne var ──")
        kok = STORAGE_ROOT / "tenants"
        if kok.exists():
            for t in list(kok.iterdir())[:3]:
                if not t.is_dir():
                    continue
                print(f"  {t.name}/")
                for alt in sorted(t.iterdir()):
                    if not alt.is_dir():
                        continue
                    try:
                        n = sum(1 for _ in alt.rglob("*") if _.is_file())
                        mb = sum(f.stat().st_size for f in alt.rglob("*")
                                 if f.is_file()) / 1024 / 1024
                        print(f"     {alt.name:<22} {n:>5} dosya  {mb:>8.1f} MB")
                    except Exception as e:  # noqa: BLE001
                        print(f"     {alt.name:<22} okunamadi: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
