#!/usr/bin/env python3
"""Mevcut katalog görselleri için duyarlı varyantları geriye dönük üret.

Yeni yüklenen görseller varyantlarını (-400/-800/-1280) yükleme anında
üretiyor (services/storage.save_catalog_image). Ama bu özellikten ÖNCE
yüklenmiş görsellerin varyantı yok; vitrin srcset onları 404 ister ve
tarayıcı kırık görsel gösterebilir. Bu betik eksikleri bir kez üretir.

Çalıştırma (VPS'te, baskici kullanıcısı):
    cd ~/baskici-saas/backend && .venv/bin/python scripts/gorsel_varyant_backfill.py
Tekrar çalıştırmak güvenli: var olan varyant atlanır (idempotent).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.images import RESPONSIVE_WIDTHS, responsive_variants
from app.services.storage import STORAGE_ROOT


def main() -> None:
    kok = STORAGE_ROOT / "tenants"
    if not kok.exists():
        print(f"storage yok: {kok}"); return
    ana_sayisi = uretilen = atlanan = hatali = 0
    for catalog in kok.glob("*/catalog"):
        for dosya in catalog.iterdir():
            govde = dosya.stem
            # Varyant dosyalarının kendisini atla ("-400" ile biten)
            if any(govde.endswith(f"-{w}") for w in RESPONSIVE_WIDTHS):
                continue
            if dosya.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                continue
            ana_sayisi += 1
            # Zaten tüm varyantlar var mı?
            var = all((dosya.parent / f"{govde}-{w}{dosya.suffix}").exists()
                      or (dosya.parent / f"{govde}-{w}.jpg").exists()
                      or (dosya.parent / f"{govde}-{w}.png").exists()
                      for w in RESPONSIVE_WIDTHS)
            if var:
                atlanan += 1
                continue
            try:
                data = dosya.read_bytes()
                for w, veri, vext in responsive_variants(data):
                    hedef = dosya.parent / f"{govde}-{w}.{vext}"
                    if not hedef.exists():
                        hedef.write_bytes(veri)
                        uretilen += 1
            except Exception as e:  # noqa: BLE001
                hatali += 1
                print(f"  HATA {dosya.name}: {e}")
    print(f"ana görsel: {ana_sayisi} · üretilen varyant: {uretilen} · "
          f"zaten tam: {atlanan} · hatalı: {hatali}")


if __name__ == "__main__":
    main()
