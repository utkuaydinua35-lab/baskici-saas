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
from sqlalchemy.orm import Session, selectinload

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
    # 1) Once tam model eslesmesi (si.model)
    for si in items:
        if _norm_var(si.variation) == nv and pm.normalize_key(si.model or "") == nm:
            return si
    # 2) Eslesmezse uyumlu modeller listesinde (si.models) ara — ortak kalip stogu
    for si in items:
        if _norm_var(si.variation) != nv:
            continue
        for cm in (si.models or []):
            if pm.normalize_key(cm) == nm:
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


def analyze_mold_stock(db: Session, tenant_id, mold) -> dict:
    """Kalibi stok acisindan analiz et (DUSMEZ, sadece raporlar).

    Donus (eski Baskici Paneli formatiyla uyumlu):
      {
        total_cases: int,
        has_stock_issues: bool,
        missing_stock: [{variation, model, need, in_stock, missing, not_in_system}],
        stock_check:   [{variation, model, count, in_stock}],
      }
    """
    need: Counter = Counter()
    variation = mold.variation
    for it in mold.items:
        if it.model:
            need[(variation, it.model)] += 1

    total_cases = sum(need.values())
    missing_stock = []
    stock_check = []

    for (var, model), qty in sorted(need.items(), key=lambda x: (x[0][1] or "")):
        si = _find_bos_kilif(db, tenant_id, var, model)
        in_stock = (si.quantity or 0) if si else 0
        if si is None:
            missing_stock.append({
                "variation": var, "model": model, "need": qty,
                "in_stock": 0, "missing": qty, "not_in_system": True,
            })
        elif in_stock < qty:
            missing_stock.append({
                "variation": var, "model": model, "need": qty,
                "in_stock": in_stock, "missing": qty - in_stock, "not_in_system": False,
            })
        else:
            stock_check.append({
                "variation": var, "model": model, "count": qty, "in_stock": in_stock,
            })

    return {
        "total_cases": total_cases,
        "has_stock_issues": len(missing_stock) > 0,
        "missing_stock": missing_stock,
        "stock_check": stock_check,
    }


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
        def _item_matches(x):
            xm = x.models if x.models else ([x.model] if x.model else [])
            return any(_norm_model(mm) == nm for mm in xm)
        si = next((x for x in cand if _item_matches(x)), None)
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


def aksesuar_talebi(db: Session, tenant_id, *,
                   stok_grubu_sart: bool = True) -> dict[tuple, dict]:
    """Acik siparislerdeki aksesuar ihtiyaci: {(grup_id, normalize_model): {...}}

    Talep = henuz kargoya VERILMEMIS (asama < 8) acik siparisler. Stok dusumu
    kargoda yapildigi icin bu siparislerin ihtiyaci hala stoktan karsilanacak.

    stok_grubu_sart=True  (EKSIK hesabi icin): yalnizca bir stok ana kalemine
        BAGLI urunler sayilir — stogu bilinmeyen urun icin "eksik" denemez.
    stok_grubu_sart=False (IHTIYAC listesi icin): baglantisi olmayanlar da
        sayilir. "Gerekli Modeller" stoga BAKMADAN "ne hazirlayacagim" diye
        sorar; orada stok grubu sarti aramak, henuz stok takibine baglanmamis
        urunleri (ornegin magsafe kiliflar) listeden tamamen dusuruyordu.
    """
    from app.models import AccessoryProduct, Order, StockGroup

    aksesuar_pids = {
        str(pid) for (pid,) in db.execute(
            select(AccessoryProduct.product_id).where(
                AccessoryProduct.tenant_id == tenant_id,
                AccessoryProduct.product_id.isnot(None),
            )
        ).all()
    }
    if not aksesuar_pids:
        return {}

    gruplar = db.scalars(
        select(StockGroup).where(StockGroup.tenant_id == tenant_id,
                                 StockGroup.is_active.is_(True))
    ).all()
    pid_to_group = {}
    for g in gruplar:
        for lp in (g.linked_products or []):
            pid = str(lp.get("product_id")) if isinstance(lp, dict) else None
            if pid:
                pid_to_group[pid] = g
    if stok_grubu_sart and not pid_to_group:
        return {}

    # ACIK siparis olcutu PAKETLEME KUYRUGUYLA ayni yerden gelir. Burada
    # yeniden yazilinca ayrisiyordu: Shopify'da fulfill edilmis, arsivlenmis
    # ve iade edilmis siparisler de "acik" sayilip listeyi sisiriyordu.
    from app.services.order_scope import acik_siparis_filtresi
    siparisler = db.scalars(
        select(Order).where(acik_siparis_filtresi(tenant_id))
    ).all()

    ihtiyac: dict[tuple, dict] = {}
    for o in siparisler:
        for li in (o.line_items or []):
            pid = str(li.product_id) if li.product_id else None
            if not pid or pid not in aksesuar_pids:
                continue
            g = pid_to_group.get(pid)
            if g is None and stok_grubu_sart:
                continue        # stok takibi yok — "eksik" denemez
            model = _extract_model_for_shipment(li)
            if not model:
                continue        # model belirlenemedi — alt kalem acilamaz
            # Gruba bagli degilse urunun kendisi kova olur; boylece ihtiyac
            # listesinde gorunur ama stok hesabina karismaz (grup_id None).
            anahtar = ((str(g.id) if g else f"urun:{pid}"), _norm_model(model))
            kayit = ihtiyac.setdefault(anahtar, {
                "grup": g.name if g else (li.title or "Aksesuar"),
                "grup_id": g.id if g else None,
                "stok_takibi": g is not None,
                "model": model, "adet": 0, "siparisler": set(),
            })
            kayit["adet"] += li.quantity or 1
            kayit["siparisler"].add(str(o.order_number))
    return ihtiyac


def aksesuar_ihtiyaci(db: Session, tenant_id) -> list[dict]:
    """Acik siparislerdeki aksesuar/islemsiz urun IHTIYACI — stok BAKILMADAN.

    Magsafe duz kilif, ekran koruyucu gibi urunler kalip planina girmiyor;
    "Gerekli Modeller" listesi kalip odakli oldugu icin onlari hic goremiyordu.
    Baskiciya "ne hazirlayacagim" derken bunlar da lazim.

    Stok kontrolu YOK: bu liste ihtiyaci soyler, eksigi degil (eksik icin
    siparis_stok_eksigi kullanilir).
    """
    # stok_grubu_sart=False: bu liste stoga BAKMAZ, ihtiyaci soyler. Stok
    # grubuna henuz baglanmamis urunler de (magsafe kiliflar gibi) gorunmeli.
    ihtiyac = aksesuar_talebi(db, tenant_id, stok_grubu_sart=False)
    out = [
        {
            "kaynak": "siparis",
            "grup": v["grup"],
            "model": v["model"] or "(model belirtilmemiş)",
            "count": v["adet"],
            "stok_takibi": v.get("stok_takibi", True),
            "siparis_sayisi": len(v["siparisler"]),
            "siparisler": sorted(v["siparisler"])[:20],
        }
        for v in ihtiyac.values()
    ]
    out.sort(key=lambda x: (-x["count"], x["model"]))
    return out


def _eslesen_alt_kalemler(db: Session, grup_ids) -> dict:
    """{grup_id(str): [StockItem]} — aktif alt kalemler, tek sorgu."""
    from app.models import StockItem as _SI
    out: dict = {}
    if not grup_ids:
        return out
    for si in db.scalars(
        select(_SI).where(_SI.group_id.in_(list(grup_ids)), _SI.is_active.is_(True))
    ).all():
        out.setdefault(str(si.group_id), []).append(si)
    return out


def _model_eslesenleri(adaylar: list, nmodel: str) -> list:
    """Alt kalemler icinde bu modele karsilik gelenler (models listesi dahil)."""
    return [
        x for x in adaylar
        if any(_norm_model(mm) == nmodel
               for mm in (x.models if x.models else ([x.model] if x.model else [])))
    ]


def kalip_stok_eksigi(db: Session, tenant_id) -> tuple[list[dict], int]:
    """Panelde duran, BASILMAMIŞ kalıplarda gereken ama rafta olmayan boş kılıflar.

    Döner: (satırlar, hesaba giren kalıp sayısı)

    ⚠ İHTİYAÇ ÖNCE TOPLANIR, STOK BİR KEZ DÜŞÜLÜR. Eskiden her kalıp AYRI AYRI
    stokla karşılaştırılıyordu: rafta 1 kılıf varken ikisi de 1'er isteyen iki
    kalıbın İKİSİ de "stok yeterli" sayılıyor, eksik hiç görünmüyordu. Aynı
    kılıf iki kalıba birden sayılamaz.
    """
    from collections import defaultdict

    from app.models import Mold
    from app.services import kalip_kapsam

    molds = db.scalars(
        select(Mold).where(Mold.tenant_id == tenant_id).options(selectinload(Mold.items))
    ).all()

    ihtiyac: Counter = Counter()
    kaliplar: dict = defaultdict(set)
    kapsamdaki = 0
    for mo in molds:
        if not kalip_kapsam.panelde_basilmamis(mo):
            continue
        kapsamdaki += 1
        for it in mo.items:
            if not (it.model or "").strip():
                continue
            anahtar = (mo.variation, it.model)
            ihtiyac[anahtar] += 1
            kaliplar[anahtar].add(str(mo.id))

    out = []
    for (var, model), adet in ihtiyac.items():
        si = _find_bos_kilif(db, tenant_id, var, model)
        mevcut = (si.quantity or 0) if si else 0
        eksik = adet - mevcut
        if eksik <= 0:
            continue
        out.append({
            "kaynak": "kalip",
            "variation": var, "model": model,
            "ihtiyac": adet, "mevcut": mevcut,
            "total_missing": eksik,
            "mold_count": len(kaliplar[(var, model)]),
            # Stokta "0" değil, KAYIT yok — sayımda hiç açılmamış demektir
            "not_in_system": si is None,
        })
    out.sort(key=lambda x: (-x["total_missing"], x["model"] or ""))
    return out, kapsamdaki


def siparis_stok_eksigi(db: Session, tenant_id) -> list[dict]:
    """Kaliba GIRMEYEN urunlerin acik siparislerdeki stok eksigi.

    Aksesuar olarak isaretli urunler (ekran koruyucu, lens, magsafe duz kilif)
    kalip planina girmez — bu yuzden kalip bazli eksik listelerinde hic
    gorunmuyorlardi. Stok bitince siparis paketlemede tikaniyor ve bunu ancak
    o an fark ediyorduk.

    Yalnizca EKSIK olanlar doner.
    """
    ihtiyac = aksesuar_talebi(db, tenant_id)
    if not ihtiyac:
        return []
    alt_kalemler = _eslesen_alt_kalemler(db, {v["grup_id"] for v in ihtiyac.values()})

    out = []
    for (gid, nmodel), v in ihtiyac.items():
        # Ayni modele birden fazla alt kalem denk gelebilir (or. ayni model,
        # farkli varyasyon). Ilkini almak, stogu olan digerini gormezden gelip
        # yanlis "eksik" uretiyordu — TUMUNUN toplami alinir.
        eslesenler = _model_eslesenleri(alt_kalemler.get(gid, []), nmodel)
        mevcut = sum(int(x.quantity or 0) for x in eslesenler)
        eksik = max(0, v["adet"] - mevcut)
        if eksik <= 0:
            continue
        out.append({
            "kaynak": "siparis",
            "grup": v["grup"],
            "model": v["model"],
            "ihtiyac": v["adet"],
            "mevcut": mevcut,
            "total_missing": eksik,
            "siparis_sayisi": len(v["siparisler"]),
            # Hangi siparislerden geldigi panelde gorunsun — "bunlar gercekten
            # acik mi?" sorusu veriyle cevaplanabilsin.
            "siparisler": sorted(v["siparisler"])[:20],
            # Alt kalem hic tanimli degil — stokta "0" degil, KAYIT yok.
            "not_in_system": not eslesenler,
        })
    out.sort(key=lambda x: (-x["total_missing"], x["model"]))
    return out
