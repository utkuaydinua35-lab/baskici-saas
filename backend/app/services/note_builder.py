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
    # 1) "X Model" formatindaki herhangi bir anahtar (Apple/Samsung/Xiaomi/Poco/Huawei/Oppo/vivo/Realme...)
    for name, val in by_name.items():
        if name.strip().lower().endswith("model") and val and str(val).strip():
            return str(val).strip()
    # 2) genel "Model"/"Telefon Modeli"
    for key in ("Model", "Telefon Modeli", "Telefon", "Phone Model"):
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


def _kalem_satir_text(k: dict) -> str:
    """Kalem dict -> tek satir metin: '1 - Galaxy S23 \"reverentia - b325\"-L9'."""
    if k.get("kalip_kodu"):
        kk = f'-{k["kalip_kodu"]}'
    else:
        kk = " (henuz kaliba eklenmedi)"
    tas = k.get("tasarim") or ""
    tas_part = f' "{tas}"' if tas else ' "?"'
    return f'{k["sira"]} - {k.get("model","?")}{tas_part}{kk}'


def build_note_lines(db: Session, tenant_id, store_id=None, dealer_id=None, gonderilmis: bool = False) -> list:
    """Siparisleri SATIR listesine cevir (checklist editoru icin).
    Her satir: {key, text, checked, kind, line_item_id, order_id, uyari}.
    kind: 'tarih' | 'siparis' | 'kalem' | 'ayrac'. (elle satirlar frontend/merge'de eklenir)
    key: auto satirlar icin stabil kimlik (merge'de checked korumak icin)."""
    content = build_note_content(db, tenant_id, store_id=store_id, dealer_id=dealer_id, gonderilmis=gonderilmis)
    lines = []
    for gun in content.get("gunler", []):
        lines.append({
            "key": f'tarih:{gun["tarih"]}',
            "text": gun["tarih"], "checked": False, "kind": "tarih",
            "line_item_id": None, "order_id": None, "uyari": None,
        })
        for sip in gun["siparisler"]:
            basl = f'{sip["order_number"]} - {sip["musteri"]} - {sip["toplam"]} ADET'
            if sip.get("not"):
                basl += f' ({sip["not"]})'
            lines.append({
                "key": f'siparis:{sip["order_id"]}',
                "text": basl, "checked": False, "kind": "siparis",
                "line_item_id": None, "order_id": sip["order_id"], "uyari": None,
            })
            for k in sip["kalemler"]:
                lines.append({
                    "key": f'kalem:{k["line_item_id"]}:{k.get("slot") or 0}',
                    "text": _kalem_satir_text(k),
                    "checked": bool(k.get("hazir")),
                    "kind": "kalem",
                    "line_item_id": k["line_item_id"],
                    "order_id": sip["order_id"],
                    "uyari": k.get("uyari"),
                })
            lines.append({
                "key": f'ayrac:{sip["order_id"]}',
                "text": "", "checked": False, "kind": "ayrac",
                "line_item_id": None, "order_id": None, "uyari": None,
            })
    return lines


def merge_lines(yeni_auto: list, mevcut: list) -> list:
    """Yenile: mevcut siparişlerin KALEM satırları taze auto kalemlerle değiştirilir
    (kalıp kodu / couple 2-kılıf güncellensin), checked korunur. Tarih/sipariş/ayraç ve
    elle eklenen (auto olmayan) satırlar korunur. Notta olmayan siparişler sona eklenir."""
    if not mevcut:
        return yeni_auto

    # Taze kalem satirlari: order_id -> [kalem satirlari]; sipariş başlığı: order_id -> satır
    fresh_kalem: dict = {}
    fresh_siparis: dict = {}
    for l in yeni_auto:
        if l.get("kind") == "kalem" and l.get("order_id"):
            fresh_kalem.setdefault(l["order_id"], []).append(l)
        elif l.get("kind") == "siparis" and l.get("order_id"):
            fresh_siparis[l["order_id"]] = l

    # checked taşımak için: key -> checked, line_item_id -> checked (yedek)
    checked_by_key = {l.get("key"): l.get("checked") for l in mevcut if l.get("kind") == "kalem"}
    checked_by_li: dict = {}
    for l in mevcut:
        if l.get("kind") == "kalem" and l.get("line_item_id") and l["line_item_id"] not in checked_by_li:
            checked_by_li[l["line_item_id"]] = l.get("checked")

    def _restore(fl):
        c = checked_by_key.get(fl.get("key"))
        if c is None:
            c = checked_by_li.get(fl.get("line_item_id"))
        return {**fl, "checked": bool(c)}

    # Mevcut'u dolaş: sipariş bloklarındaki eski kalemleri taze kalemlerle değiştir
    out = []
    mevcut_order_ids = set()
    i, n = 0, len(mevcut)
    while i < n:
        l = mevcut[i]
        if l.get("order_id"):
            mevcut_order_ids.add(l["order_id"])
        if l.get("kind") == "siparis" and l.get("order_id") in fresh_kalem:
            oid = l["order_id"]
            # başlık metnini tazele (ADET/couple sayısı güncellensin)
            if oid in fresh_siparis:
                l = {**l, "text": fresh_siparis[oid]["text"]}
            out.append(l)
            for fl in fresh_kalem[oid]:
                out.append(_restore(fl))
            # eski kalem satirlarini atla (kind==kalem oldugu surece)
            j = i + 1
            while j < n and mevcut[j].get("kind") == "kalem":
                j += 1
            i = j
            continue
        out.append(l)
        i += 1
    mevcut = out

    # Notta hic olmayan siparisleri sona ekle (tarih basligi + blok)
    yeni_eklenecek = []
    i, n = 0, len(yeni_auto)
    pending_tarih = None
    while i < n:
        l = yeni_auto[i]
        if l.get("kind") == "tarih":
            pending_tarih = l
            i += 1
            continue
        if l.get("kind") == "siparis":
            oid = l.get("order_id")
            blok = [l]
            j = i + 1
            while j < n and yeni_auto[j].get("kind") in ("kalem", "ayrac"):
                blok.append(yeni_auto[j])
                j += 1
            if oid and oid not in mevcut_order_ids:
                if pending_tarih is not None:
                    tarih_var = any(m.get("kind") == "tarih" and m.get("text") == pending_tarih.get("text") for m in mevcut)
                    tarih_eklendi = any(e.get("kind") == "tarih" and e.get("text") == pending_tarih.get("text") for e in yeni_eklenecek)
                    if not tarih_var and not tarih_eklendi:
                        yeni_eklenecek.append(pending_tarih)
                yeni_eklenecek.extend(blok)
            i = j
            continue
        i += 1
    return mevcut + yeni_eklenecek


def build_note_content(db: Session, tenant_id, store_id=None, dealer_id=None, gonderilmis: bool = False) -> dict:
    """Bir magaza/bayii icin not icerigini (auto_content) uret.
    gonderilmis=False -> acik siparisler, True -> gonderilmis siparisler."""
    q = (
        select(Order)
        .where(
            Order.tenant_id == tenant_id,
            Order.is_iptal == False,  # noqa: E712
            Order.is_telafi == False,  # noqa: E712  telafiler notlara girmez
        )
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

    # Kalip kodu eslestirme: MoldItem (line_item_id COGU ZAMAN None) -> order_number + design_code ile esle.
    # Kisa kod (K3/L6): Mold.kod "K3-K7-L6" + Mold.kalip_kodlari [grup1,grup2,grup3] paralel listeler.
    # MoldItem.kalip_kodu (grup) -> Mold.kalip_kodlari index -> Mold.kod.split("-")[index].
    from app.models import Mold as _Mold, CoupleProduct as _Couple
    from app.services import phone_models as _pm
    from app.services.mold_planner import extract_couple_models as _extract_couple_models

    def _nk(s):
        try:
            return _pm.normalize_key(s or "")
        except Exception:  # noqa: BLE001
            return (s or "").strip().upper()

    order_numbers = [o.order_number for o in orders if o.order_number]
    # Kademeli kalip kisa-kod eslesmesi (line_item_id senkronda NULL olabilir):
    by_liid: dict = {}                 # line_item_id -> kisa
    by_oc: dict = {}                   # (order_number, design_code) -> kisa
    by_om: dict = {}                   # (order_number, model_norm) -> kisa
    by_o: dict = {}                    # order_number -> kisa (son care)
    if order_numbers:
        mis = db.scalars(select(MoldItem).where(MoldItem.order_number.in_(order_numbers))).all()
        mold_cache: dict = {}
        for mi in mis:
            if mi.mold_id not in mold_cache:
                md = db.get(_Mold, mi.mold_id)
                kodlar = (md.kod or "").split("-") if md and md.kod else []
                gruplar = md.kalip_kodlari if md and md.kalip_kodlari else []
                mold_cache[mi.mold_id] = (kodlar, gruplar)
            kodlar, gruplar = mold_cache[mi.mold_id]
            kisa = None
            if mi.kalip_kodu in gruplar:
                idx = gruplar.index(mi.kalip_kodu)
                if idx < len(kodlar):
                    kisa = kodlar[idx]
            if not kisa:
                continue
            onum = str(mi.order_number)
            if mi.line_item_id:
                by_liid[str(mi.line_item_id)] = kisa
            if mi.design_code:
                by_oc[(onum, str(mi.design_code))] = kisa
            if mi.model:
                by_om[(onum, _nk(mi.model))] = kisa
            by_o[onum] = kisa

    # Katalog tasarımları: (store_id, product_id, variant_id) -> Design (mold_planner ile ayni
    # mantik). Kisiye ozel olmayan kalemlerin tasarim kodunu cozup kalip eslesmesinde kullaniriz;
    # boylece ayni modelden farkli tasarimli kalemler dogru kalibi gosterir.
    design_by_key: dict = {}
    for d in db.scalars(select(Design).where(Design.tenant_id == tenant_id, Design.product_id.isnot(None))).all():
        pid = str(d.product_id)
        vid = str(d.variant_id) if getattr(d, "variant_id", None) else None
        design_by_key[(d.store_id, pid, vid)] = d
        if vid is None or (d.store_id, pid, None) not in design_by_key:
            design_by_key[(d.store_id, pid, None)] = d

    def _li_design(li, store_id):
        if li.assigned_design:
            return li.assigned_design
        if li.product_id:
            pid = str(li.product_id)
            vid = str(li.variant_id) if getattr(li, "variant_id", None) else None
            return design_by_key.get((store_id, pid, vid)) or design_by_key.get((store_id, pid, None))
        return None

    # Couple ürünler — 2 kılıf (slot 1/2) olarak yazılmalı
    couple_rows = db.scalars(select(_Couple).where(_Couple.tenant_id == tenant_id)).all()
    couple_map = {(c.store_id, str(c.product_id)): c for c in couple_rows}
    _cdesign_ids = {x for c in couple_rows for x in (c.design_id_1, c.design_id_2) if x}
    design_by_id: dict = {}
    if _cdesign_ids:
        for d in db.scalars(select(Design).where(Design.id.in_(_cdesign_ids))).all():
            design_by_id[d.id] = d

    def _kk_for(onum, li_id, dcode, model):
        return (by_liid.get(str(li_id))
                or (dcode and by_oc.get((onum, str(dcode))))
                or by_om.get((onum, _nk(model)))
                or by_o.get(onum))

    # gune gore grupla
    gunler_map: dict = {}  # sira_key -> {"tarih": gorunen, "siparisler": []}
    for o in orders:
        dt = o.created_at_platform
        tarih = dt.strftime("%d.%m") if dt else "??.??"
        sira_key = dt.date().isoformat() if dt else "9999-99-99"  # gercek tarih siralamasi icin
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
        onum = str(o.order_number)
        gonderildi = (o.fulfillment_status == "fulfilled")
        for li in sorted(o.line_items or [], key=lambda x: x.position or 0):
            qty = li.quantity or 1
            couple = couple_map.get((o.store_id, str(li.product_id))) if li.product_id else None

            if couple is not None:
                # Couple = 2 kılıf (slot 1 + 2), her biri ayrı satır + adet
                if couple.is_kisiye_ozel:
                    d1, d2 = li.assigned_design, li.assigned_design_2
                    m1 = (li.device_model_override or "").strip() or (_model_from_props(li) or "?")
                    m2 = (li.device_model_override_2 or "").strip() or m1
                else:
                    d1 = design_by_id.get(couple.design_id_1) if couple.design_id_1 else None
                    d2 = design_by_id.get(couple.design_id_2) if couple.design_id_2 else None
                    _cm1, _cm2 = _extract_couple_models(li)
                    m1 = _cm1 or (_model_from_props(li) or "?")
                    m2 = _cm2 or m1
                for slot, d, m in ((1, d1, m1), (2, d2, m2)):
                    tas, uyari = _tasarim_str(li, d)
                    dcode = str(d.code) if d and d.code else None
                    sira += 1
                    toplam += qty
                    kalemler.append({
                        "line_item_id": str(li.id), "slot": slot, "sira": sira,
                        "model": m, "tasarim": tas,
                        "kalip_kodu": _kk_for(onum, li.id, dcode, m),
                        "kaliba_eklendi": bool(li.is_kaliba_eklendi),
                        "hazir": gonderildi, "uyari": uyari,
                    })
                continue

            # Tekli kalem — tasarımı (kişiye özel ya da katalog) çözüp kodundan eşleştir
            model = _model_from_props(li) or "?"
            li_design = _li_design(li, o.store_id)
            tasarim, uyari = _tasarim_str(li, li_design)
            _dcode = str(li_design.code) if li_design and li_design.code else None
            sira += 1
            toplam += qty
            kalemler.append({
                "line_item_id": str(li.id), "slot": None, "sira": sira,
                "model": model, "tasarim": tasarim,
                "kalip_kodu": _kk_for(onum, li.id, _dcode, model),
                "kaliba_eklendi": bool(li.is_kaliba_eklendi),
                "hazir": gonderildi, "uyari": uyari,
            })

        if sira_key not in gunler_map:
            gunler_map[sira_key] = {"tarih": tarih, "siparisler": []}
        gunler_map[sira_key]["siparisler"].append({
            "order_id": str(o.id),
            "order_number": o.order_number,
            "musteri": musteri,
            "toplam": toplam,
            "not": (raw.get("note") or "").strip() or None,
            "kalemler": kalemler,
        })

    # gunleri sirali liste yap (tarihe gore — string ama gun.ay formatinda)
    gunler = []
    for sk in sorted(gunler_map.keys()):  # ISO tarih -> eskiden yeniye dogru
        gunler.append({"tarih": gunler_map[sk]["tarih"], "siparisler": gunler_map[sk]["siparisler"]})

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
