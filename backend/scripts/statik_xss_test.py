"""/storage ve /uploads: SVG/HTML script çalıştırabilir mi?

NEDEN VAR: SafeStaticFiles bu korumayı yazıldığı günden beri UYGULAMIYORDU.
`Path` app/main.py'de import edilmemişti; her istekte NameError fırlıyor,
çıplak `except Exception` yutuyor ve uzantı boş kalıyordu — yani riskli
uzantı dalı hiç çalışmadı. Kod "doğru görünüyordu", davranış yanlıştı.

Zincir: /api/shop/{slug}/studio/assets KİMLİKSİZ SVG kabul ediyor → dosya
/storage altına yazılıyor → nginx /storage'ı PANEL alan adında servis ediyor
→ panelde yönetici JWT'si localStorage'da. Inline çalışan bir SVG, yöneticinin
oturumunu çalabilirdi.

Bu test davranışı sınar, kodu değil: dosyayı gerçekten ister ve BAŞLIKLARA
bakar. Koruma tekrar sessizce ölürse burası kırmızıya döner.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services import storage as storage_svc  # noqa: E402
from app.services import uploads as uploads_svc  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


C = TestClient(app)
IZ = uuid.uuid4().hex[:8]
ZARARLI = (b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(document.domain)">'
           b'<script>alert(1)</script></svg>')

# Dosyaları doğrudan diske koyuyoruz: sınanan şey YÜKLEME değil, SERVİS.
kokler = [(storage_svc.STORAGE_ROOT, "/storage"), (uploads_svc.UPLOAD_ROOT, "/uploads")]
yazilan: list[Path] = []
for kok, onek in kokler:
    kok.mkdir(parents=True, exist_ok=True)
    for uzanti, govde in (("svg", ZARARLI), ("html", b"<script>alert(1)</script>"),
                          ("xml", b"<?xml version='1.0'?><x/>")):
        p = kok / f"xsstest-{IZ}.{uzanti}"
        p.write_bytes(govde)
        yazilan.append(p)

try:
    for _kok, onek in kokler:
        print(f"\n── {onek} ──")
        for uzanti in ("svg", "html", "xml"):
            r = C.get(f"{onek}/xsstest-{IZ}.{uzanti}")
            es(f"{uzanti}: bulundu", 200, r.status_code)
            ct = (r.headers.get("content-type") or "").lower()
            cd = (r.headers.get("content-disposition") or "").lower()
            csp = (r.headers.get("content-security-policy") or "").lower()
            # ASIL SÖZ: tarayıcı bunu çalıştırmamalı.
            es(f"{uzanti}: inline DEĞİL (attachment)", True, "attachment" in cd)
            es(f"{uzanti}: çalıştırılabilir tip DEĞİL", False,
               "svg" in ct or "html" in ct or "xml" in ct)
            es(f"{uzanti}: CSP script'i engelliyor", True, "default-src 'none'" in csp)
            es(f"{uzanti}: nosniff", "nosniff",
               (r.headers.get("x-content-type-options") or "").lower())

    print("\n── zararsız görsel hâlâ inline (gerileme yok) ──")
    png = storage_svc.STORAGE_ROOT / f"xsstest-{IZ}.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 32)
    yazilan.append(png)
    r = C.get(f"/storage/xsstest-{IZ}.png")
    es("png: 200", 200, r.status_code)
    es("png: attachment DEĞİL", False,
       "attachment" in (r.headers.get("content-disposition") or "").lower())
    es("png: image/png", True,
       "image/png" in (r.headers.get("content-type") or "").lower())
finally:
    for p in yazilan:
        p.unlink(missing_ok=True)

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
