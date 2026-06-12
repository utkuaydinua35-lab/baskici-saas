"""
Stok servisi — fiziksel stok takibi + kalıp basıldı düşümü.

Kategoriler: bos_kilif | ekran_koruyucu | lens_koruyucu | diger
Boş kılıf eşleşmesi: category=bos_kilif + variation (siyah/beyaz/şeffaf/parlak/magsafe)
+ model (telefon modeli; phone_models.normalize_key ile karşılaştırılır).

Düşüm: Kalıp stage 5 (Tamamlandı = basıldı) olunca, kalıbın her item'ı için
1 boş kılıf düşülür. İDEMPOTENT: aynı kalıp için 'mold_basildi' hareketi varsa
tekrar düşmez (stage ileri-geri olursa çift düşüm olmaz).
"""
from __future__ import annotations

import uuid
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StockItem, StockMovement
from app.services import phone_models as pm

CATEGORIES = ["bos_kilif", "ekran_koruyucu", "lens_koruyucu", "diger"]
DEFAULT_VARIATIONS = ["siyah", "beyaz", "şeffaf", "parlak", "magsafe"]

# Stok düşümünü tetikleyen mold aşaması (5 = Tamamlandı / basıldı)
DEDUCT_MOLD_STAGE = 5


def _norm_var(s: str | None) -> str:
    """Varyasyon normalizasyonu (TR-duyarsız, büyük harf)."""
    if not s:
        return ""
    s = s.strip().upper()
    for a, b in [("Ş", "S"), ("Ç", "C"), ("Ö", "O"), ("Ü", "U"), ("Ğ", "G"), ("İ", "I"), ("I", "I")]:
        s = s.replace(a, b)
    return s


def _move(db: Session, item: StockItem, delta: int, reason: str, *,
          ref_mold_id=None, ref_order_id=None, note=None, created_by=None) -> StockMovement:
    """Stok hareketini uygula (quantity güncelle) + kayıt oluştur."""
    item.quantity = (item.quantity or 0) + delta
    mv = StockMovement(
        tenant_id=item.tenant_id,
        stock_item_id=item.id,
        delta=delta,
        balance_after=item.quantity,
        reason=reason,
        ref_mold_id=ref_mold_id,
        ref_order_id=ref_order_id,
        note=note,
        created_by=created_by,
    )
    db.add(mv)
    return mv


def apply_adjustment(db: Session, item: StockItem, delta: int, reason: str,
                     note: str | None = None, created_by: str | None = None) -> StockMovement:
    """Manuel giriş/çıkış/düzeltme. delta>0 giriş, delta<0 çıkış."""
    return _move(db, item, delta, reason, note=note, created_by=created_by)


def _find_bos_kilif(db: Session, tenant_id, variation: str | None, model: str | None) -> StockItem | None:
    """category=bos_kilif + variation + model eşleşen aktif stok kalemini bul."""
    items = db.scalars(
        select(StockItem).where(
            StockItem.tenant_id == tenant_id,
            StockItem.category == "bos_kilif",
            StockItem.is_active.is_(True),
        )
    ).all()
    nv = _norm_var(variation)
    nm = pm.normalize_key(model or "")
    for si in items:
        if _norm_var(si.variation) == nv and pm.normalize_key(si.model or "") == nm:
            return si
    return None


def deduct_for_mold(db: Session, tenant_id, mold, user=None) -> dict:
    """Kalıp basıldığında boş kılıf stoğunu düş. İdempotent.

    Dönüş: {already, deducted, shortages:[...], lines:[...]}
    - already=True → bu kalıp için zaten düşülmüş, hiçbir şey yapılmadı.
    - shortages → eşleşen stok yok ya da yetersiz (stage geçişi BLOKLANMAZ).
    """
    already = db.scalar(
        select(StockMovement.id).where(
            StockMovement.tenant_id == tenant_id,
            StockMovement.reason == "mold_basildi",
            StockMovement.ref_mold_id == mold.id,
        ).limit(1)
    )
    if already:
        return {"already": True, "deducted": 0, "shortages": [], "lines": []}

    created_by = getattr(user, "email", None) if user else None

    need: Counter = Counter()
    variation = mold.variation
    for it in mold.items:
        if it.model:
            need[(variation, it.model)] += 1

    deducted = 0
    shortages = []
    lines = []
    for (var, model), qty in need.items():
        si = _find_bos_kilif(db, tenant_id, var, model)
        if not si:
            shortages.append({"variation": var, "model": model, "need": qty, "reason": "stok_kalemi_yok"})
            continue
        take = min(si.quantity or 0, qty)
        if take > 0:
            _move(
                db, si, -take, "mold_basildi",
                ref_mold_id=mold.id,
                note=f"Kalıp {mold.kod} basıldı",
                created_by=created_by,
            )
            deducted += take
            lines.append({"sku": si.sku, "variation": var, "model": model, "deducted": take})
        if take < qty:
            shortages.append({
                "variation": var, "model": model,
                "need": qty, "deducted": take, "reason": "yetersiz_stok",
            })

    return {"already": False, "deducted": deducted, "shortages": shortages, "lines": lines}


def _extract_model_for_shipment(li) -> str | None:
    """Line item'tan telefon modeli cikar (mold_planner ile ayni heuristic)."""
    try:
        from app.services import mold_planner
        return mold_planner.extract_phone_model(li)
    except Exception:
        # fallback: variant_title ilk parca
        if getattr(li, "device_model_override", None):
            return li.device_model_override
        if getattr(li, "variant_title", None):
            return li.variant_title.split("/")[0].strip()
        return None


def _norm_model(s: str | None) -> str:
    # Onceligi case_dimensions normalize key'e ver (siparis modeli ile stok modeli ayni key'e gelsin)
    try:
        from app.services._private import case_dimensions as cd
        k = cd._normalize_to_spec_key(s or "")
        if k:
            return k
    except Exception:
        pass
    return (s or "").strip().lower().replace("ı", "i").replace("İ", "i")


def deduct_for_shipment(db: Session, tenant_id, order, user=None) -> dict:
    """Siparis kargoya verilince: her kalemin urunu bagli oldugu ana kalemde,
    kalemin modeline karsilik gelen alt kalem stogundan dus. Idempotent.

    Donus: {already, deducted, shortages, lines}
    """
    from app.models import StockGroup, StockItem as _SI
    # Idempotent: bu siparis icin zaten dusulmus mu?
    already = db.scalar(
        select(StockMovement.id).where(
            StockMovement.tenant_id == tenant_id,
            StockMovement.reason == "siparis_kargoda",
            StockMovement.ref_order_id == order.id,
        ).limit(1)
    )
    if already:
        return {"already": True, "deducted": 0, "shortages": [], "lines": []}

    created_by = getattr(user, "email", None) if user else None

    # Tum ana kalemleri + bagli urun id'lerini hazirla
    groups = db.scalars(
        select(StockGroup).where(StockGroup.tenant_id == tenant_id, StockGroup.is_active.is_(True))
    ).all()
    # product_id -> group eslesmesi
    pid_to_group = {}
    for g in groups:
        for lp in (g.linked_products or []):
            pid = str(lp.get("product_id")) if isinstance(lp, dict) else None
            if pid:
                pid_to_group[pid] = g

    deducted = 0
    shortages = []
    lines = []
    for li in (order.line_items or []):
        pid = str(li.product_id) if li.product_id else None
        if not pid or pid not in pid_to_group:
            continue  # bu kalem bir ana kaleme bagli degil
        g = pid_to_group[pid]
        model = _extract_model_for_shipment(li)
        if not model:
            shortages.append({"group": g.name, "model": None, "reason": "model_belirlenemedi"})
            continue
        # gruptaki modele uyan alt kalem (varyasyon yoksa sadece model)
        cand = db.scalars(
            select(_SI).where(_SI.group_id == g.id, _SI.is_active.is_(True))
        ).all()
        nm = _norm_model(model)
        si = next((x for x in cand if _norm_model(x.model) == nm), None)
        qty = li.quantity or 1
        if not si:
            shortages.append({"group": g.name, "model": model, "need": qty, "reason": "alt_kalem_yok"})
            continue
        take = min(si.quantity or 0, qty)
        if take > 0:
            _move(db, si, -take, "siparis_kargoda",
                  ref_order_id=order.id,
                  note=f"Siparis #{getattr(order, 'order_number', '?')} kargoda",
                  created_by=created_by)
            deducted += take
            lines.append({"group": g.name, "model": model, "deducted": take})
        if take < qty:
            shortages.append({"group": g.name, "model": model, "need": qty, "deducted": take, "reason": "yetersiz_stok"})

    return {"already": False, "deducted": deducted, "shortages": shortages, "lines": lines}
