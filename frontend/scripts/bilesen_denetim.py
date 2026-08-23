"""JSX'te kullanılan ama TANIMLI OLMAYAN bileşenleri bul.

Vite bunu derlemede yakalamıyor: <Foo /> tanımsızsa build geçer, sayfa
çalışma anında "Foo is not defined" ile beyaz ekrana düşer. Bu hata bu
projede iki kez yaşandı (MoldGeneratorPage'de PdfRozet, OrdersPage'de
onDone={load}).

ESLint'i açmak yerine yalnız bu sınıfı sınıyoruz — proje lint'i 199 uyarıyla
dolu, oraya kural eklemek pratikte kullanılmıyor.

Kullanım:
    cd frontend && python3 scripts/bilesen_denetim.py
Çıkış kodu 1 = eksik bileşen var.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent / "src"

# <Foo ...> / <Foo.Bar ...> — büyük harfle başlayanlar bileşendir
KULLANIM = re.compile(r"<([A-Z][A-Za-z0-9_]*)")
TANIM = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:function|const|class)\s+([A-Z][A-Za-z0-9_]*)", re.M)
IMPORT_SATIR = re.compile(r"^\s*import\s+(.+?)\s+from\s+['\"]", re.M)

# React'in kendi sözdizimi / bilinen global bileşenler
MUAF = {"Fragment", "Suspense", "StrictMode", "Profiler"}


def _yorumlari_ayikla(kaynak: str) -> str:
    """Blok ve satır yorumlarını çıkar.

    Yorum içindeki örnek JSX ("* <Route element={<ProtectedRoute />}>") gerçek
    kullanım sanılıp yanlış alarm üretiyordu.
    """
    kaynak = re.sub(r"/\*[\s\S]*?\*/", " ", kaynak)
    return re.sub(r"(?m)^\s*//.*$", " ", kaynak)


def _import_adlari(kaynak: str) -> set[str]:
    adlar: set[str] = set()
    for parca in IMPORT_SATIR.findall(kaynak):
        parca = parca.strip()
        # import Foo, { Bar as Baz } from '...'
        for kume in re.findall(r"\{([^}]*)\}", parca):
            for p in kume.split(","):
                p = p.strip()
                if not p:
                    continue
                adlar.add(p.split(" as ")[-1].strip())
        dis = re.sub(r"\{[^}]*\}", "", parca).replace("*", " ")
        for p in dis.split(","):
            p = p.strip().split(" as ")[-1].strip()
            if p:
                adlar.add(p)
    return adlar


def main() -> None:
    eksikler: list[tuple[str, str]] = []
    for f in sorted(KOK.rglob("*.jsx")):
        ham = f.read_text(encoding="utf-8")
        src = _yorumlari_ayikla(ham)
        tanimli = set(TANIM.findall(ham)) | _import_adlari(ham) | MUAF
        for ad in sorted(set(KULLANIM.findall(src))):
            if ad not in tanimli:
                eksikler.append((str(f.relative_to(KOK.parent)), ad))

    if not eksikler:
        print("✓ Tanımsız bileşen yok.")
        return
    print("✗ Kullanılan ama tanımlı/import edilmemiş bileşenler:\n")
    for dosya, ad in eksikler:
        print(f"  {dosya}: <{ad}>")
    print(f"\n{len(eksikler)} sorun. Bunlar derlemede değil, SAYFA AÇILIRKEN patlar.")
    sys.exit(1)


if __name__ == "__main__":
    main()
