"""Native kabuk (Capacitor) API'ye ulaşabiliyor mu?

Uygulama web sayfasını KENDİ origin'inde açar: iOS'ta capacitor://localhost,
Android'de http://localhost. Bu origin'ler CORS listesinde olmazsa
uygulamanın HER isteği preflight'ta 400 alır ve uygulama hiç çalışmaz —
üstelik hata mesajı "ERR_FAILED" olduğu için sebebi anlaşılmaz.

GÜVENLİK NOTU: origin eklemek bu API'de kimlik sınırını gevşetmez. Kimlik
Authorization: Bearer ile doğrulanıyor, çerezle değil; CORS zaten bir kimlik
mekanizması değil. Test bunu da sınıyor: listede OLMAYAN origin hâlâ
reddediliyor.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


C = TestClient(app)


def izinli_mi(origin: str) -> bool:
    """Tarayıcı bu origin'den istek atabilir mi (CORS başlığı dönüyor mu)?"""
    r = C.options("/api/auth/login", headers={
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    return r.headers.get("access-control-allow-origin") == origin


print("\n── native kabuk origin'leri API'ye ulaşabilmeli ──")
for o in ("capacitor://localhost", "http://localhost", "https://localhost"):
    es(f"{o} izinli", True, izinli_mi(o))

print("\n── liste HÂLÂ sıkı: yabancı origin reddediliyor ──")
for o in ("https://kotu.example", "http://evil.localhost.attacker.com",
          "capacitor://baska"):
    es(f"{o} REDDEDİLDİ", False, izinli_mi(o))

print("\n── gerçek istekte de başlık dönüyor (preflight yetmez) ──")
r = C.post("/api/auth/login", headers={"Origin": "capacitor://localhost"},
           json={"email": "yok@yok.example", "password": "x"})
es("yanıtta allow-origin var", "capacitor://localhost",
   r.headers.get("access-control-allow-origin"))
es("kimlik hâlâ zorunlu (401)", 401, r.status_code)

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
