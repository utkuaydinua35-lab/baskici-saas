"""Basit Kargo hesabındaki gönderici adreslerini / markaları / anlaşmaları listele.

Kendi anlaşma (SELF_*) gönderilerinde Basit Kargo hangi gönderici adresiyle ve
hangi anlaşmayla çıkılacağını bilmek zorunda. BASIT_KARGO_ADDRESS_ID (ve varsa
BASIT_KARGO_BRAND_ID) .env'de tanımlı değilse istek eksik gidiyor ve
"HTTP 500 · Kargo oluşturulamadı." dönüyor.

Bu betik ilgili uçları sorgular, kimlikleri ekrana basar. Çıkan id'yi .env'e yaz:
    BASIT_KARGO_ADDRESS_ID=...
    BASIT_KARGO_BRAND_ID=...

Kullanım (VPS, baskici kullanıcısı):
    cd ~/baskici-saas/backend && .venv/bin/python scripts/basit_kargo_bilgi.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

from app.services.basit_kargo import BASE_URL, _headers, is_configured  # noqa: E402

# Hesap yapılandırmasını taşıyabilecek uçlar. Hepsi her hesapta olmayabilir —
# 404/405 normaldir, atlanır.
UCLAR = [
    ("Gönderici adresleri", "/firm/address"),
    ("Markalar", "/firm/brand"),
    ("Anlaşmalar/handler'lar", "/firm/handler"),
    ("Firma bilgisi", "/firm"),
]


def _yaz(veri, girinti: str = "    ") -> None:
    """Listeyi id + tanımlayıcı alanlarıyla yaz; tanınmayan yapıyı ham bas."""
    if isinstance(veri, dict):
        for anahtar in ("data", "items", "result", "content"):
            if anahtar in veri and isinstance(veri[anahtar], (list, dict)):
                _yaz(veri[anahtar], girinti)
                return
        veri = [veri]
    if not isinstance(veri, list):
        print(f"{girinti}{veri}")
        return
    if not veri:
        print(f"{girinti}(boş)")
        return
    for e in veri:
        if not isinstance(e, dict):
            print(f"{girinti}{e}")
            continue
        _id = e.get("id") or e.get("Id") or e.get("_id") or "—"
        _ad = (e.get("name") or e.get("title") or e.get("code")
               or e.get("handlerCode") or "")
        _ek = " · ".join(str(e[k]) for k in ("city", "town", "address", "phone")
                         if e.get(k))
        print(f"{girinti}id={_id}  {_ad}" + (f"  [{_ek[:70]}]" if _ek else ""))


def main() -> None:
    if not is_configured():
        print("BASIT_KARGO_TOKEN tanımlı değil (.env).")
        return
    for baslik, yol in UCLAR:
        print(f"\n═══ {baslik}  (GET {yol})")
        try:
            r = requests.get(f"{BASE_URL}{yol}", headers=_headers(), timeout=20)
        except Exception as e:  # noqa: BLE001
            print(f"    bağlantı hatası: {str(e)[:120]}")
            continue
        if r.status_code in (404, 405):
            print("    bu hesapta yok / desteklenmiyor")
            continue
        if r.status_code != 200:
            print(f"    HTTP {r.status_code}: {(r.text or '')[:160]}")
            continue
        try:
            _yaz(r.json())
        except json.JSONDecodeError:
            print(f"    {(r.text or '')[:300]}")

    print("\n" + "─" * 60)
    print("Gönderici adresi id'sini .env'e ekle, sonra servisi yeniden başlat:")
    print("    BASIT_KARGO_ADDRESS_ID=<yukarıdaki id>")
    print("    BASIT_KARGO_BRAND_ID=<marka id — varsa>")


if __name__ == "__main__":
    main()
