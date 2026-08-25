"""Ürün açıklamalarını temizleyiciden geçir (geriye dönük).

sanitize_rich_text yazma anında uygulanıyor; ancak temizleyici EKLENMEDEN
ÖNCE kaydedilmiş açıklamalar ham duruyor olabilir ve vitrin onları
dangerouslySetInnerHTML ile basıyor.

Varsayılan KURU ÇALIŞMA — sadece raporlar. Uygulamak için:
    .venv/bin/python scripts/aciklama_temizle.py --uygula
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import CatalogProduct  # noqa: E402
from app.services.sanitize import sanitize_rich_text  # noqa: E402

UYGULA = "--uygula" in sys.argv

TEHLIKE = re.compile(
    r"<\s*(script|iframe|style|svg|object|embed|form|meta|link|base)\b"
    r"|\son\w+\s*=|javascript:|data:text/html", re.I)

db = SessionLocal()
urunler = db.scalars(select(CatalogProduct)).all()

degisen, tehlikeli = [], []
for p in urunler:
    ham = p.description or ""
    if not ham:
        continue
    temiz = sanitize_rich_text(ham) or ""
    if temiz == ham:
        continue
    degisen.append(p)
    if TEHLIKE.search(ham):
        tehlikeli.append(p)

print(f"Ürün sayısı           : {len(urunler)}")
print(f"Açıklaması değişecek  : {len(degisen)}")
print(f"  ↳ TEHLİKELİ içerikli: {len(tehlikeli)}")
print()

for p in degisen[:20]:
    isaret = "⚠ TEHLİKELİ" if p in tehlikeli else "·"
    print(f"  {isaret} {p.slug}")
    print(f"      önce : {(p.description or '')[:100]!r}")
    print(f"      sonra: {(sanitize_rich_text(p.description) or '')[:100]!r}")
if len(degisen) > 20:
    print(f"  … ve {len(degisen) - 20} tane daha")

if not degisen:
    print("✓ Temizlenecek bir şey yok — tüm açıklamalar zaten güvenli.")
elif UYGULA:
    for p in degisen:
        p.description = sanitize_rich_text(p.description)
    db.commit()
    print(f"\n✓ {len(degisen)} açıklama temizlendi ve kaydedildi.")
else:
    print("\nKURU ÇALIŞMA — hiçbir şey değiştirilmedi.")
    print("Uygulamak için: .venv/bin/python scripts/aciklama_temizle.py --uygula")
