"""Bağımlılıksız .xlsx okuyucu — kargo firması export'larını içe aktarmak için.

xlsx zaten bir zip + XML; openpyxl kurmadan okuyoruz (VPS'e ek paket gerekmesin,
deploy riski olmasın). Yalnızca OKUMA yapar, formül/biçim yorumlamaz.

Kullanım:
    satirlar = read_rows(dosya_baytlari)   # [{"TakipNo": "...", "Alici": "..."}]
"""
from __future__ import annotations

import io
import zipfile
from xml.etree import ElementTree as ET

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
MAX_SATIR = 20000


class XlsxError(Exception):
    pass


def _sutun_harfi(ref: str) -> str:
    """'AG12' -> 'AG'"""
    return "".join(c for c in (ref or "") if c.isalpha())


def _shared_strings(z: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    kok = ET.fromstring(z.read("xl/sharedStrings.xml"))
    out = []
    for si in kok.findall("m:si", _NS):
        out.append("".join(n.text or "" for n in si.iter() if n.tag.endswith("}t")))
    return out


def _sheet_adi(z: zipfile.ZipFile) -> str:
    """İlk çalışma sayfasının XML yolu. Dosyadan dosyaya degisebiliyor
    (sheet.xml / sheet1.xml), o yuzden sabit isim varsaymiyoruz."""
    adaylar = [n for n in z.namelist()
               if n.startswith("xl/worksheets/") and n.endswith(".xml")]
    if not adaylar:
        raise XlsxError("Çalışma sayfası bulunamadı — geçerli bir .xlsx değil.")
    return sorted(adaylar)[0]


def _hucre_degeri(c, shared: list[str]) -> str:
    t = c.get("t")
    if t == "inlineStr":
        return "".join(n.text or "" for n in c.iter() if n.tag.endswith("}t")).strip()
    v = c.find("m:v", _NS)
    if v is None or v.text is None:
        return ""
    if t == "s":
        try:
            return (shared[int(v.text)] or "").strip()
        except (ValueError, IndexError):
            return ""
    return (v.text or "").strip()


def read_rows(data: bytes) -> list[dict]:
    """İlk satırı BAŞLIK kabul edip sözlük listesi döndür.

    Boş başlıklı sütunlar atlanır. Tamamen boş satırlar atlanır.
    """
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise XlsxError("Dosya okunamadı — .xlsx değil ya da bozuk.") from e
    try:
        shared = _shared_strings(z)
        sh = ET.fromstring(z.read(_sheet_adi(z)))
    except ET.ParseError as e:
        raise XlsxError("Dosya içeriği çözümlenemedi.") from e

    satirlar = sh.findall(".//m:row", _NS)
    if not satirlar:
        return []

    basliklar: dict[str, str] = {}
    for c in satirlar[0].findall("m:c", _NS):
        ad = _hucre_degeri(c, shared)
        if ad:
            basliklar[_sutun_harfi(c.get("r") or "")] = ad
    if not basliklar:
        raise XlsxError("İlk satırda başlık bulunamadı.")

    out: list[dict] = []
    for r in satirlar[1:]:
        if len(out) >= MAX_SATIR:
            break
        kayit: dict[str, str] = {}
        for c in r.findall("m:c", _NS):
            kol = basliklar.get(_sutun_harfi(c.get("r") or ""))
            if kol:
                kayit[kol] = _hucre_degeri(c, shared)
        if any(v for v in kayit.values()):
            out.append(kayit)
    return out


def sutun_bul(satir: dict, *adaylar: str) -> str:
    """Başlık adları firmadan firmaya değişir; ilk eşleşen sütunun değerini ver.

    Karşılaştırma boşluk/büyük-küçük harf duyarsız ve KISMİ eşleşmelidir
    ('Alıcı Adı Soyadı' ~ 'alici').
    """
    def _n(s: str) -> str:
        s = (s or "").replace("İ", "i").replace("I", "ı").lower()
        return "".join(ch for ch in s.translate(
            str.maketrans("ığüşöçâî", "igusocai")) if ch.isalnum())

    normal = {_n(k): v for k, v in satir.items()}
    for a in adaylar:
        na = _n(a)
        if na in normal:
            return normal[na]
    for a in adaylar:
        na = _n(a)
        for k, v in normal.items():
            if na and (na in k or k in na):
                return v
    return ""
