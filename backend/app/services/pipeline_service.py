"""
Pipeline ana servisi.

İş akışı:
1. Store + kısayollar + KalipKodlari hazırla
2. Her order için _process_order_for_pipeline çağır
3. Items'ları kalıp koduna göre grupla
4. Bin-pack (kalıp birleştirme)
5. Output metni üret (Illustrator-uyumlu + raw)
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Order, Shortcut, Store
from app.services import pipeline_helpers as ph
from app.services.kalip_kodlari import (
    KalipKodlari,
    build_kalip_kodlari,
    get_kalip_kodu_full,
    get_kalip_kodu_iphone_only,
    get_model_group_simple,
    get_variation_for_code,
    variation_header,
)

# Bin-pack sabitleri (BERNZ)
KALIP_MAX_BOXES = 27
KALIP_COLS = 9
KALIP_ROWS = 3

# Aksesuar (pipeline'a hiç girmez)
ACCESSORY_EXCLUDE_KEYWORDS = [
    "ekran koruyucu", "lens koruyucu", "screen protector",
    "hayalet ekran koruyucu", "anti-statik ekran koruyucu",
    "telefon hoparlör koruyucu", "toz geçirmez hoparlör koruyucusu",
    "silikon vantuzlu telefon tutucu",
]

# Bu kelimeleri içeren ürünlerde kısayol araması yapılmaz
SHORTCUT_EXCLUDE_KEYWORDS = ["ekran koruyucu", "lens koruyucu", "screen protector"]


# ─── Tek sipariş işleme ──────────────────────────────────────

def _process_one_order(
    order_dict: dict,
    kisayollar: dict[str, str],
    kk: KalipKodlari,
    strategy: str,  # "full" | "simple"
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Bir Shopify order dict'ini işle.
    Dönüş: (items, missing, kisiye_ozel)
    """
    order_num = str(order_dict.get("order_number") or order_dict.get("name", "").replace("#", ""))
    customer = order_dict.get("customer", {}) or {}
    cust_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
    is_yurtici = ph.get_shipping_method_yurtici(order_dict)

    items: list[dict] = []
    missing: list[dict] = []
    kisiye_ozel: list[dict] = []

    is_lunera = (strategy == "simple")

    for li in order_dict.get("line_items", []) or []:
        qty = li.get("quantity", 1)
        full_title = li.get("title", "")
        full_title_lower = full_title.lower()

        # Aksesuar — atla
        if any(kw in full_title_lower for kw in ACCESSORY_EXCLUDE_KEYWORDS):
            continue

        # Kişiye özel kontrolü
        props = li.get("properties") or []
        props_text = " ".join((p.get("value", "") or "") for p in props).lower()
        combined_text = full_title_lower + " " + props_text

        if "kişiye özel" in combined_text or "kisiye ozel" in combined_text:
            img_url = ""
            for p in props:
                pval = (p.get("value") or "").strip()
                if pval.startswith("http") and not img_url:
                    img_url = pval
            for _ in range(qty):
                kisiye_ozel.append({
                    "order_num": order_num,
                    "customer": cust_name,
                    "title": full_title,
                    "image_url": img_url,
                })
            continue

        # Kısayol hariç tutma
        skip_shortcut = any(kw in full_title_lower for kw in SHORTCUT_EXCLUDE_KEYWORDS)

        # MagSafe (sadece BERNZ/Lunera/Casiva — 505 değil)
        # Şu an store başına yönetim yapmıyoruz; ileride store ayarı olabilir.
        # if not skip_shortcut and "magsafe" in full_title_lower:
        #     skip_shortcut = True

        if is_lunera:
            # Lunera/Casiva — basit kısayol + sadece iPhone
            phone = ph.extract_phone_model_lunera(li)
            design_raw = ph.extract_design_name_lunera(li) or full_title
            design, renk = ph.apply_kisayol_simple(design_raw, kisayollar)
            shortcut_found = (design != design_raw)
            kod = get_kalip_kodu_iphone_only(phone, design, renk, kk, full_title)

        else:
            # BERNZ/505 — tam kısayol, COUPLE destekli
            phone = ph.extract_phone_model_from_properties(li)
            if not phone:
                vt = (li.get("variant_title") or "").strip()
                if vt and vt.lower() not in ["default title", "default", ""]:
                    phone = vt
            design_raw = ph.extract_design_name_from_title(li)
            option_value = ph.extract_option_value(li)
            result, data = ph.apply_kisayol_full(design_raw, kisayollar, option_value, full_title)
            shortcut_found = (result != design_raw) or (result == "COUPLE")

            # COUPLE handling
            if result == "COUPLE" and isinstance(data, list) and len(data) >= 2:
                m1, m2 = ph.extract_phone_models_couple(li)
                for ci, (d, r) in enumerate(data[:2]):
                    cp = m1 if ci == 0 else m2
                    ck = get_kalip_kodu_full(cp, d, r, kk, full_title)
                    for _ in range(qty):
                        items.append({
                            "order_num": order_num,
                            "customer": cust_name,
                            "phone": cp or "",
                            "design": d,
                            "renk": r,
                            "kod": ck,
                            "yurtici": is_yurtici,
                            "is_couple": True,
                            "model_group": get_model_group_simple(cp),
                        })
                # COUPLE işlendi, normal akışa devam etme
                continue

            design = result
            renk = data if isinstance(data, str) else ""
            kod = get_kalip_kodu_full(phone, design, renk, kk, full_title)

        # Eksik kısayol tespiti (kişiye özel hariç)
        if not shortcut_found and not skip_shortcut and design_raw:
            if design_raw.lower() not in ["kişiye özel", "kişiye özel -"]:
                missing.append({
                    "design": design_raw,
                    "phone": phone or "",
                    "order_num": order_num,
                })

        for _ in range(qty):
            items.append({
                "order_num": order_num,
                "customer": cust_name,
                "phone": phone or "",
                "design": design,
                "renk": renk,
                "kod": kod,
                "yurtici": is_yurtici,
                "is_couple": False,
                "model_group": get_model_group_simple(phone),
            })

    return items, missing, kisiye_ozel


# ─── Bin-pack ────────────────────────────────────────────────

def _count_rows(items_list: list[dict]) -> int:
    """Item listesinin kaç satır kaplayacağı (model grubu başına ayrı satır)."""
    group_counts: dict[str, int] = {}
    for it in items_list:
        mg = it.get("model_group", "UNKNOWN")
        group_counts[mg] = group_counts.get(mg, 0) + 1
    total = 0
    for count in group_counts.values():
        total += -(-count // KALIP_COLS)  # ceil
    return total


def _can_merge_kalips(a: dict, b: dict) -> bool:
    if a["count"] + b["count"] > KALIP_MAX_BOXES:
        return False
    if a["variation"] != b["variation"]:
        return False
    return _count_rows(a["items"] + b["items"]) <= KALIP_ROWS


def _do_merge_kalips(a: dict, b: dict) -> None:
    a["names"].extend(b["names"])
    a["items"].extend(b["items"])
    a["count"] = len(a["items"])
    a["isMerged"] = True
    if "groupVariations" not in a:
        a["groupVariations"] = {a["names"][0]: a["variation"]}
    for n in b["names"]:
        a["groupVariations"][n] = b["variation"]


def bin_pack_kalips(queue: list[dict]) -> list[dict]:
    """Aynı varyasyondaki kalıpları birleştir (kapasiteyi aşmadan)."""
    if len(queue) <= 1:
        return queue
    queue.sort(key=lambda x: x["count"], reverse=True)
    bins: list[dict] = []
    for item in queue:
        placed = False
        for b in bins:
            if _can_merge_kalips(b, item):
                _do_merge_kalips(b, item)
                placed = True
                break
        if not placed:
            bins.append({
                "names": list(item["names"]),
                "items": list(item["items"]),
                "count": item["count"],
                "variation": item["variation"],
                "isMerged": False,
                "groupVariations": {item["names"][0]: item["variation"]},
            })
    for b in bins:
        b["names"].sort()
    return bins


def bin_pack_by_variation(kalip_queue: list[dict]) -> list[dict]:
    """Önce varyasyona böl, sonra her grup içinde merge."""
    siyah_q = [k for k in kalip_queue if k["variation"] == "SİYAH"]
    beyaz_q = [k for k in kalip_queue if k["variation"] == "BEYAZ"]
    seffaf_q = [k for k in kalip_queue if k["variation"] == "ŞEFFAF"]
    parlak_q = [k for k in kalip_queue if k["variation"] == "PARLAK"]
    other_q = [k for k in kalip_queue if k["variation"] not in
               ("SİYAH", "BEYAZ", "ŞEFFAF", "PARLAK")]
    return (bin_pack_kalips(siyah_q) + bin_pack_kalips(beyaz_q)
            + bin_pack_kalips(seffaf_q) + bin_pack_kalips(parlak_q)
            + other_q)


# ─── Render output ───────────────────────────────────────────

def render_kalip_output(optimized: list[dict], include_kodsuz: list[dict] | None = None) -> str:
    """
    Bin-packed kalıpları okunabilir metne çevir (Illustrator-uyumlu).
    """
    output_lines: list[str] = []
    for kalip in optimized:
        var_h = variation_header(kalip["variation"])
        display_name = " ".join(kalip["names"])
        header = f"{display_name} ({kalip['count']} ADET){var_h}"
        output_lines.append(header)

        sorted_items = sorted(
            kalip["items"],
            key=lambda x: (x.get("_source_kod", "ZZZ"), x.get("model_group", "ZZZ"))
        )
        is_merged = kalip.get("isMerged", False)
        for item in sorted_items:
            line = f'- [{item["order_num"]}] {item["phone"]} "{item["design"]}"'
            if item.get("yurtici"):
                line += " 🔵"
            if is_merged and item.get("_source_kod"):
                line += f"  [{item['_source_kod']}]"
            output_lines.append(line)
        output_lines.append("")

    if include_kodsuz:
        output_lines.append(f"⚠ KODSUZ ({len(include_kodsuz)} ADET)")
        for item in include_kodsuz:
            output_lines.append(f'- [{item["order_num"]}] {item["phone"]} "{item["design"]}"')

    return "\n".join(output_lines).strip()


def render_raw_output(groups: dict[str, list[dict]], kk: KalipKodlari) -> str:
    """Birleştirilmemiş — her kalıp kodu ayrı blok."""
    output_lines: list[str] = []
    for kod in sorted(groups.keys()):
        items_list = groups[kod]
        if not items_list:
            continue
        variation = get_variation_for_code(kod, kk)
        var_h = variation_header(variation)

        for it in items_list:
            it["_source_kod"] = kod

        output_lines.append(f"{kod} ({len(items_list)} ADET){var_h}")
        sorted_items = sorted(items_list, key=lambda x: x.get("model_group", "ZZZ"))
        for item in sorted_items:
            line = f'- [{item["order_num"]}] {item["phone"]} "{item["design"]}"'
            if item.get("yurtici"):
                line += " 🔵"
            line += f"  [{kod}]"
            output_lines.append(line)
        output_lines.append("")
    return "\n".join(output_lines).strip()


# ─── Ana process fonksiyonu ──────────────────────────────────

def process_pipeline(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    store_id: uuid.UUID,
    order_numbers: list[str],
    letters: str,
) -> dict[str, Any]:
    """
    Ana pipeline çalıştırması.

    1. Store + kısayollar + kalıp kodları hazırla
    2. DB'deki order'ları (raw JSON'dan) işle
    3. Bin-pack
    4. Output üret
    """
    # Store
    store = db.scalar(
        select(Store).where(Store.id == store_id, Store.tenant_id == tenant_id)
    )
    if not store:
        raise ValueError("Mağaza bulunamadı")

    strategy = store.matching_strategy or "full"

    # Kalıp kodları
    kk = build_kalip_kodlari(letters, strategy)

    # Kısayollar
    shortcut_rows = db.scalars(
        select(Shortcut).where(Shortcut.store_id == store_id)
    ).all()
    kisayollar = {s.key: s.value for s in shortcut_rows}

    # Order'lar (numbers'a göre, DB'de olanlar)
    orders = db.scalars(
        select(Order)
        .where(
            Order.store_id == store_id,
            Order.order_number.in_(order_numbers),
        )
        .options(selectinload(Order.line_items))
    ).all()

    found_order_nums = {o.order_number for o in orders}
    not_found = [n for n in order_numbers if n not in found_order_nums]

    # Process her order
    all_items: list[dict] = []
    all_missing: list[dict] = []
    all_kisiye_ozel: list[dict] = []
    errors: list[str] = []

    for order in orders:
        try:
            # raw JSON'u kullan — line_items orijinal yapıda
            items, missing, kisiye = _process_one_order(
                order.raw, kisayollar, kk, strategy,
            )
            all_items.extend(items)
            all_missing.extend(missing)
            all_kisiye_ozel.extend(kisiye)
        except Exception as e:
            errors.append(f"Sipariş #{order.order_number}: {str(e)[:200]}")

    # Kalıp kodu olmayanları ayır
    kodsuz = [it for it in all_items if not it.get("kod")]
    kodlu = [it for it in all_items if it.get("kod")]

    # Kod bazında grupla
    groups: dict[str, list[dict]] = {}
    for it in kodlu:
        groups.setdefault(it["kod"], []).append(it)

    # Bin-pack için queue oluştur (her grup bir queue item)
    queue: list[dict] = []
    for kod, items_list in groups.items():
        variation = get_variation_for_code(kod, kk)
        queue.append({
            "names": [kod],
            "items": items_list,
            "count": len(items_list),
            "variation": variation,
        })

    # Bin-pack + render
    optimized = bin_pack_by_variation(queue)

    # Her item'a kaynak kod yaz (merge sonrası takip için)
    for kalip in optimized:
        if kalip.get("isMerged"):
            # Hangi item hangi kod'dan geldi, groupVariations'tan bul
            pass  # zaten _do_merge_kalips items'ı topluyor
        for it in kalip["items"]:
            if not it.get("_source_kod"):
                it["_source_kod"] = kalip["names"][0]

    illustrator_output = render_kalip_output(optimized, kodsuz if kodsuz else None)
    raw_output = render_raw_output(groups, kk)

    # Missing'i unique yap (aynı tasarım birden fazla kez gelirse)
    seen_designs = set()
    unique_missing: list[dict] = []
    for m in all_missing:
        key = (m.get("design", "").lower(), m.get("phone", "").lower())
        if key in seen_designs:
            continue
        seen_designs.add(key)
        unique_missing.append(m)

    return {
        "stats": {
            "total_orders": len(orders),
            "not_found_orders": len(not_found),
            "total_items": len(all_items),
            "kodlu_items": len(kodlu),
            "kodsuz_items": len(kodsuz),
            "missing_shortcuts": len(unique_missing),
            "kisiye_ozel": len(all_kisiye_ozel),
            "kalip_count": len(optimized),
        },
        "not_found": not_found,
        "items": all_items,
        "missing": unique_missing,
        "kisiye_ozel": all_kisiye_ozel,
        "kalips": [
            {
                "name": " ".join(k["names"]),
                "names": k["names"],
                "count": k["count"],
                "variation": k["variation"],
                "is_merged": k.get("isMerged", False),
                "items": k["items"],
            }
            for k in optimized
        ],
        "illustrator_output": illustrator_output,
        "raw_output": raw_output,
        "errors": errors,
        "kalip_kodlari": kk.to_dict(),
    }
