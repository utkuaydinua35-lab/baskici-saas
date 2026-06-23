"""Siparis -> not formati uretimi (Apple Notes tarzi).

Cikti format (gorsel ornegi):
    17.06
    11236 - ZUHAL INCEOGLU - 6 ADET
    1 - Galaxy S23 "reverentia - b325"-L9
    4 - iPhone 11 "king baldwin portrait - b763"-K2 [HAZIR]
    .
    11237 - YIGIT KORKMAZ - 3 ADET
    ...

auto_content yapisi (JSON):
{
  "gunler": [
    {
      "tarih": "17.06",
      "siparisler": [
        {
          "order_id": "...", "order_number": "11236", "musteri": "ZUHAL INCEOGLU",
          "toplam": 6, "not": null,
          "kalemler": [
            {"sira": 1, "model": "Galaxy S23", "tasarim": "reverentia - b325",
             "kalip_kodu": "L9", "kaliba_eklendi": true, "hazir": false, "uyari": null}
          ]
        }
      ]
    }
  ]
}
"""
from __future__ import annotations

import re
import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Order, LineItem, Design, MoldItem, Store


def _model_from_props(li: LineItem) -> str | None:
    """properties'ten telefon modelini cikar: 'Apple Model'/'Samsung Model' degeri."""
    props = li.properties or []
    by_name = {}
    for p in props:
        n = p.get("name") if isinstance(p, dict) else None
        if n and not n.startswith("_"):
            by_name[n] = p.get("value")
    # Once spesifik model alanlari
    for key in ("Apple Model", "Samsung Model", "Xiaomi Model", "Model", "Telefon Modeli"):
        if by_name.get(key):
            return by_name[key]
    # variant_title fallback (Lunera/Casiva: model variant_title'da, orn "iPhone 16 Pro")
    if li.variant_title and li.variant_title.strip():
        return li.variant_title.strip()
    # device_model_override fallback
    if li.device_model_override:
        return li.device_model_override
    return None


_TITLE_DESIGN_RE = re.compile(r'[\u2018\u2019\u201c\u201d"\']([^\u2018\u2019\u201c\u201d"\']{2,})[\u2018\u2019\u201c\u201d"\']')


def _design_from_title(title: str | None) -> str | None:
    """Urun basligindan tasarim adini cikar (tirnak ici): 'Reverentia' Tasarim... -> Reverentia."""
    if not title:
        return None
    m = _TITLE_DESIGN_RE.search(title)
    if m:
        return m.group(1).strip()
    return None


def _tasarim_str(li: LineItem, design: Design | None) -> tuple[str, str | None]:
    """(tasarim_metni, uyari). design varsa 'name - code', isim yoksa uyari."""
    if design:
        name = (design.name or "").strip()
        code = (design.code or "").strip()
        if name and code:
            return f"{name} - {code}", None
        if code and not name:
            return code, "tasarim adi eksik"
        if name and not code:
            return name, "tasarim kodu eksik"
        return "", "tasarim adi/kodu eksik"
    # Tasarim atanmamis: baslitan cikar
    fallback = _design_from_title(li.title)
    if fallback:
        return fallback, "tasarim henuz atanmadi"
    return "", "tasarim atanmadi"


def build_note_content(db: Session, tenant_id, store_id=None, dealer_id=None, gonderilmis: bool = False) -> dict:
    """Bir magaza/bayii icin not icerigini (auto_content) uret.
    gonderilmis=False -> acik siparisler, True -> gonderilmis siparisler."""
    q = (
        select(Order)
        .where(Order.tenant_id == tenant_id, Order.is_iptal == False)  # noqa: E712
        .options(selectinload(Order.line_items).selectinload(LineItem.assigned_design))
        .order_by(Order.created_at_platform.asc())
    )
    if store_id:
        q = q.where(Order.store_id == store_id)
    # acik vs gonderilmis
    if gonderilmis:
        q = q.where(Order.fulfillment_status == "fulfilled")
    else:
        q = q.where((Order.fulfillment_status != "fulfilled") | (Order.fulfillment_status.is_(None)))

    orders = db.scalars(q).all()

    # bayii filtresi (raw.dealer_id)
    if dealer_id:
        orders = [o for o in orders if (o.raw or {}).get("dealer_id") == str(dealer_id)]
    elif store_id:
        # ana magaza notu: bayii siparislerini disla
        orders = [o for o in orders if not (o.raw or {}).get("dealer_id")]

    # MoldItem kalip kodlarini topla (line_item_id -> kalip_kodu)
    li_ids = [li.id for o in orders for li in (o.line_items or [])]
    mold_map: dict = {}
    if li_ids:
        for mi in db.scalars(select(MoldItem).where(MoldItem.line_item_id.in_(li_ids))).all():
            mold_map[mi.line_item_id] = mi.kalip_kodu

    # gune gore grupla
    gunler_map: dict = defaultdict(list)
    for o in orders:
        dt = o.created_at_platform
        tarih = dt.strftime("%d.%m") if dt else "??.??"
        raw = o.raw or {}
        cust = raw.get("customer") or {}
        musteri = ""
        if cust:
            musteri = (str(cust.get("first_name", "")) + " " + str(cust.get("last_name", ""))).strip()
        if not musteri:
            musteri = raw.get("customer_phone") or raw.get("customer_name") or "?"
        musteri = musteri.upper()

        kalemler = []
        sira = 0
        toplam = 0
        for li in sorted(o.line_items or [], key=lambda x: x.position or 0):
            adet = li.quantity or 1
            toplam += adet
            sira += 1
            model = _model_from_props(li) or "?"
            tasarim, uyari = _tasarim_str(li, li.assigned_design)
            kk = mold_map.get(li.id)
            kalemler.append({
                "line_item_id": str(li.id),
                "sira": sira,
                "model": model,
                "tasarim": tasarim,
                "kalip_kodu": kk,  # None ise "henuz kaliba eklenmedi"
                "kaliba_eklendi": bool(li.is_kaliba_eklendi),
                "hazir": bool(li.is_hazir),
                "uyari": uyari,
            })

        gunler_map[tarih].append({
            "order_id": str(o.id),
            "order_number": o.order_number,
            "musteri": musteri,
            "toplam": toplam,
            "not": (raw.get("note") or "").strip() or None,
            "kalemler": kalemler,
        })

    # gunleri sirali liste yap (tarihe gore — string ama gun.ay formatinda)
    gunler = []
    for tarih in sorted(gunler_map.keys()):
        gunler.append({"tarih": tarih, "siparisler": gunler_map[tarih]})

    return {"gunler": gunler, "siparis_sayisi": len(orders)}


def render_note_text(auto_content: dict) -> str:
    """auto_content -> duz metin (gorsel format). Frontend ham metin de isteyebilir."""
    lines = []
    for gun in auto_content.get("gunler", []):
        lines.append(gun["tarih"])
        for sip in gun["siparisler"]:
            baslik = f'{sip["order_number"]} - {sip["musteri"]} - {sip["toplam"]} ADET'
            if sip.get("not"):
                baslik += f' ({sip["not"]})'
            lines.append(baslik)
            for k in sip["kalemler"]:
                if k["kalip_kodu"]:
                    kk = f'-{k["kalip_kodu"]}'
                else:
                    kk = " (henuz kaliba eklenmedi)"
                tas = k["tasarim"] or ""
                satir = f'{k["sira"]} - {k["model"]} "{tas}"{kk}'
                if k["hazir"]:
                    satir += " [HAZIR]"
                if k.get("uyari"):
                    satir += f' [!{k["uyari"]}]'
                lines.append(satir)
            lines.append(".")
    return "\n".join(lines)
