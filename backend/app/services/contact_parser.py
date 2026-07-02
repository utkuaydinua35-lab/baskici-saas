"""Serbest metin (Instagram/WhatsApp'tan yapıştırılan) kişi/adres bilgisini ayrıştır.

Örn girdi:
    ramazan taş
    fırat mahallesi 96031 nolu sokak no 34 Şahinbey Gaziantep Türkiye
    +90 546 815 91 02

Çıktı: {name, phone, address, il, ilce}
"""
from __future__ import annotations

import re

from app.services import tr_iller

# TR cep telefonu: +90 / 0 önekli ya da öneksiz 5xx xxx xx xx (aralarda boşluk/nokta/tire olabilir)
_PHONE_RE = re.compile(
    r"(?:\+?9?0?[\s.\-()]*)?5\d{2}[\s.\-()]*\d{3}[\s.\-()]*\d{2}[\s.\-()]*\d{2}"
)


def normalize_phone(raw: str | None) -> str:
    d = re.sub(r"\D", "", raw or "")
    if d.startswith("90") and len(d) == 12:
        d = d[2:]
    if len(d) == 10 and d.startswith("5"):
        d = "0" + d
    return d  # 11 hane: 05xxxxxxxxx (tanınmazsa ham rakam)


def _detect_il(text: str) -> str | None:
    """Metinde geçen il adını bul (son geçen kazanır — adres genelde 'ilçe il' ile biter)."""
    # noktalama -> boşluk (virgül vb. bitişik 'Konya,' eşleşmesin diye)
    clean = re.sub(r"[^\w\s]", " ", text or "")
    tn = " " + tr_iller._norm(clean) + " "
    found, pos = None, -1
    for il in tr_iller.IL_ILCE:
        idx = tn.rfind(" " + tr_iller._norm(il) + " ")
        if idx > pos:
            pos, found = idx, il
    return found


def _strip_location(addr: str, il: str | None, ilce: str | None) -> str:
    """Adres metninden il/ilçe/Türkiye kelimelerini çıkar."""
    drop = set()
    for t in (il, ilce, "Türkiye", "Turkey"):
        if t:
            drop.add(tr_iller._norm(t))
    kept = [w for w in addr.split() if tr_iller._norm(w.strip(",.")) not in drop]
    return re.sub(r"\s+", " ", " ".join(kept)).strip(" ,")


def _title(s: str) -> str:
    return " ".join(w[:1].upper() + w[1:] for w in (s or "").split())


def parse_contact(text: str) -> dict:
    text = (text or "").strip()
    empty = {"name": "", "phone": "", "address": "", "il": "", "ilce": ""}
    if not text:
        return empty

    # 1) Telefon
    phone, rest = "", text
    m = _PHONE_RE.search(text)
    if m:
        phone = normalize_phone(m.group(0))
        rest = (text[:m.start()] + " " + text[m.end():]).strip()

    # 2) İl (metinden) → yoksa posta kodundan (5 haneli)
    il = _detect_il(rest)
    if not il:
        zm = re.search(r"\b(\d{5})\b", rest)
        if zm:
            il = tr_iller.PLAKA.get(int(zm.group(1)[:2]))
    ilce = tr_iller.ilce_bul(rest, il) if il else None

    lines = [ln.strip() for ln in rest.splitlines() if ln.strip()]

    # 3) İsim: rakamsız + il/ilçe içermeyen ilk satır
    name = ""
    for ln in lines:
        if re.search(r"\d", ln):
            continue
        lnn = tr_iller._norm(ln)
        if il and tr_iller._norm(il) in lnn:
            continue
        if ilce and tr_iller._norm(ilce) in lnn:
            continue
        name = ln
        break
    if not name and lines:
        # Tek satır / virgüllü girdi: ilk virgülden önceki rakamsız kısmı isim say
        first = lines[0]
        head = first.split(",")[0].strip()
        name = head if head and not re.search(r"\d", head) else first

    # 4) Adres: rakam içeren en uzun satır (isim hariç); il/ilçe/Türkiye kırpılır
    addr_cands = [ln for ln in lines if ln != name and re.search(r"\d", ln)]
    if addr_cands:
        address = max(addr_cands, key=len)
    else:
        address = " ".join(ln for ln in lines if ln != name)
    address = _strip_location(address, il, ilce)

    return {
        "name": _title(name),
        "phone": phone,
        "address": address,
        "il": il or "",
        "ilce": ilce or "",
    }
