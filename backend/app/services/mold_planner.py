"""
Kalıp planlayıcı — bekleyen sipariş kalemlerini otomatik kalıplara böler.

Multi-store (Paket 20): store_id None ise tenant'taki TÜM aktif mağazaların
siparişlerini birleştirir. Bir kalıp satırında (örn A1) birden çok mağazadan
kalem karışabilir; baskı üretiminde mağaza farkı yok, kargo etiketi aşamasında
her slot'un kendi store_id'si üzerinden ayrılır.
"""
from __future__ import annotations

import hashlib
import re
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import AccessoryProduct, CoupleProduct, Design, KisiyeOzelProduct, LineItem, Order, Store
from app.services import katalog_tasarim, placement_rules as pr, storage


def extract_phone_model(line_item: LineItem) -> str | None:
    """properties içinde adı ' Model' ile biten kaydın değeri = telefon modeli.
    device_model_override öncelikli."""
    if getattr(line_item, "device_model_override", None):
        return line_item.device_model_override
    for p in (line_item.properties or []):
        if isinstance(p, dict):
            name = (p.get("name") or "")
            if name.endswith("Model") and not name.startswith("_"):
                val = (p.get("value") or "").strip()
                if val:
                    return val
    # properties'te yoksa variant_title'a dus (orn. Lunera: variant_title = "iPhone 16 Pro")
    vt = (getattr(line_item, "variant_title", None) or "").strip()
    if vt:
        return vt
    # son care: raw.variant_title
    raw = getattr(line_item, "raw", None)
    if isinstance(raw, dict):
        rvt = (raw.get("variant_title") or "").strip()
        if rvt:
            return rvt
    return None


# Müşterinin seçtiği kılıf varyasyonu — KESİN anahtar eşleşmesi (yanlış pozitif düşük).
# Spesifik olanlar önce; SİYAH en sonda (varsayılan/zayıf).
# "OFF WHITE" bir MARKA/desen adi, kilif rengi degil. Onune bakmadan WHITE
# eslestirmek "OFF WHITE Just Black" adli SIYAH tasarimlari BEYAZ kaliba
# sokuyordu (yanlis renk baski = maddi zarar).
_MARKA_YANLIS = re.compile(r"\bOFF[\s-]?WHITE\b")
_VAR_PATTERNS = [
    ("BEYAZ", re.compile(r"(?<!OFF )(?<!OFF-)\b(BEYAZ|WHITE)\b")),
    ("ŞEFFAF", re.compile(r"\b(ŞEFFAF|SEFFAF|CLEAR|TRANSPARAN)\b")),
    ("PARLAK", re.compile(r"\b(PARLAK|GLITTER|SİMLİ|SIMLI)\b")),
    ("MAGSAFE", re.compile(r"\b(MAGSAFE|MAG ?SAFE)\b")),
    ("SİYAH", re.compile(r"\b(SİYAH|SIYAH|BLACK)\b")),
]
# Bu isimlerden birini taşıyan property = kılıf tipi/varyasyon alanı (en güvenilir kaynak).
_CASE_HINT = re.compile(r"KILIF|KILIF|RENK|VARYASYON|KAPAK|COVER|CASE|COLOR|TİP|TIP", re.I)


def _match_variation(text: str) -> str | None:
    t = (text or "").upper()
    # Marka adini once cikar: "OFF WHITE" icindeki WHITE renk degil.
    t = _MARKA_YANLIS.sub(" ", t)
    for var, pat in _VAR_PATTERNS:
        if pat.search(t):
            return var
    return None


def variation_from_props(line_item) -> str | None:
    """Müşterinin line item property'lerinden seçtiği kılıf varyasyonu (SİYAH/BEYAZ/ŞEFFAF/
    PARLAK/MAGSAFE) ya da None. İsmi kılıf/renk/tip içeren property en güvenilir; yoksa
    herhangi bir property değerindeki açık eşleşme."""
    other = None
    for p in (line_item.properties or []):
        if not isinstance(p, dict):
            continue
        name = p.get("name") or ""
        if name.startswith("_"):
            continue
        v = _match_variation(p.get("value") or "")
        if not v:
            continue
        if _CASE_HINT.search(name):
            return v          # isim ipuçlu alan -> doğrudan kullan
        if other is None:
            other = v          # ipuçsuz ama değer eşleşti -> yedek
    return other


def _tasarim_adini_cikar(metin: str, design) -> str:
    """Ürün adından TASARIM ADINI çıkar.

    Ürün adı çoğu zaman tasarım adını içeriyor ("OFF WHITE Just Black Telefon
    Kılıfı"). Tasarım adındaki renk kelimeleri KILIF rengi değil, desenin adı.
    Onları çıkarınca geriye kalan kısım gerçekten kılıfı tarif eder
    ("... Special PARLAK Telefon Kılıfı" gibi).
    """
    if design is None:
        return metin
    out = metin
    for alan in ("name", "code"):
        ad = (getattr(design, alan, None) or "").strip()
        if len(ad) >= 3:
            out = re.sub(re.escape(ad), " ", out, flags=re.I)
    return out


def variation_from_title(line_item, design=None) -> str | None:
    """Ürün/varyant ADINDAKİ kılıf varyasyonu — örn "... BERNZ Special PARLAK Telefon Kılıfı".

    Müşterinin satın aldığı ürünün adı, tasarımın varsayılan kalip_tipi'sinden
    DAHA belirleyicidir: property'de varyasyon yoksa buraya bakılır.

    AMA tasarım adı ürün adının içindeyse önce ÇIKARILIR — yoksa desen adındaki
    renk kelimesi kılıf rengi sanılıyor ("OFF WHITE ..." adlı siyah tasarımlar
    beyaz kalıba giriyordu).
    """
    for t in (getattr(line_item, "variant_title", None), getattr(line_item, "title", None)):
        v = _match_variation(_tasarim_adini_cikar(t or "", design))
        if v:
            return v
    return None


def resolve_line_variation(line_item, design=None, slot: int = 1) -> str | None:
    """TEK KAYNAK: bir kalemin kılıf varyasyonunu çöz (SİYAH/BEYAZ/ŞEFFAF/PARLAK/MAGSAFE).

    Öncelik (en güvenilirden zayıfa):
      1. Kaleme ELLE atanan varyasyon (kişiye özel panel / vitrin / varyant)
      2. Müşterinin property seçimi (Shopify seçenekleri)
      3. ÜRÜN/VARYANT ADI — örn "... Special PARLAK Telefon Kılıfı"
      4. Tasarımın varsayılan kalip_tipi'si
    Hiçbiri yoksa None (çağıran 'varyasyon eksik' olarak işaretlemeli — SESSİZCE
    SİYAH'a düşmek yanlış üretime yol açıyordu).

    Üretim (kalıp), müşteri onay görseli ve panel aynı sonucu görsün diye HER YERDE
    bu fonksiyon kullanılır.
    """
    return resolve_line_variation_detail(line_item, design, slot)[0]


# Kaynak etiketi -> panelde gösterilecek Türkçe açıklama
VARIATION_SOURCE_LABELS = {
    "elle": "Elle seçildi",
    "ozellik": "Müşteri seçimi (ürün özelliği)",
    "urun_adi": "Ürün adından okundu",
    "tasarim": "Tasarımın varsayılanı",
}


def resolve_line_variation_detail(line_item, design=None, slot: int = 1) -> tuple:
    """(varyasyon, kaynak) — kaynak: elle | ozellik | urun_adi | tasarim | None.

    Varyasyonun NEREDEN geldiği panelde gösterilebilsin diye ayrı fonksiyon:
    "tasarımda siyah yazıyordu ama beyaz kalıba girdi" tipi durumlarda hangi
    kaynağın kazandığı tek bakışta görünsün.
    """
    from app.services import placement_rules as _pr
    _attr = "kilif_varyasyon_2" if slot == 2 else "kilif_varyasyon"
    manual = (getattr(line_item, _attr, None) or "").strip()
    if manual:
        return _pr.normalize_variation(manual), "elle"
    v = variation_from_props(line_item)
    if v:
        return v, "ozellik"
    v = variation_from_title(line_item, design)
    if v:
        return v, "urun_adi"
    dkt = ((getattr(design, "kalip_tipi", None) or "").strip() if design is not None else "")
    if dkt:
        return _pr.normalize_variation(dkt), "tasarim"
    return None, None


def _li_property_values(line_item) -> list[str]:
    """Line item property DEĞERLERİ (casefold), internal (_) hariç."""
    out = []
    for p in (line_item.properties or []):
        if not isinstance(p, dict):
            continue
        if (p.get("name") or "").startswith("_"):
            continue
        v = (p.get("value") or "").strip()
        if v:
            out.append(v.casefold())
    return out


def match_variant_design(line_item, variant_list):
    """variant_list: [(match_norm, Design)] (match_norm casefold). Müşterinin property'den
    seçtiği değere göre eşleşen varyant tasarımı; yoksa None. Önce tam, sonra içerme eşleşmesi."""
    if not variant_list:
        return None
    vals = _li_property_values(line_item)
    if not vals:
        return None
    for mv, d in variant_list:
        if any(v == mv for v in vals):
            return d
    for mv, d in variant_list:
        if mv and any(mv in v or v in mv for v in vals):
            return d
    return None


def extract_couple_models(line_item: LineItem) -> tuple[str | None, str | None]:
    """Couple urun: properties'ten 2 telefon modeli cikar.
    1. model (erkek) = ' Model' ile biten ilk kayit (orn 'Apple Model').
    2. model (kadin) = ' Model copy' / ' Model 2' gibi ikinci model kaydi.
    Donus: (model1, model2). model2 yoksa None."""
    model1 = None
    model2 = None
    for p in (line_item.properties or []):
        if not isinstance(p, dict):
            continue
        name = (p.get("name") or "")
        if name.startswith("_"):
            continue
        val = (p.get("value") or "").strip()
        if not val:
            continue
        low = name.lower()
        # 2. model: 'model copy', 'model 2', 'model2', 'model (2)' vb.
        if "model" in low and (low.endswith("copy") or low.rstrip().endswith("2") or "copy" in low or " 2" in low):
            if model2 is None:
                model2 = val
        elif name.endswith("Model"):
            if model1 is None:
                model1 = val
    return model1, model2


def couple_tasarim_idleri(db, line_item) -> tuple:
    """Couple kalemin İKİ tasarım id'si — TEK KAYNAK.

    Tasarım İKİ yerden gelebiliyor:
      • kişiye özel couple  -> kalemin assigned_design_id / _2 alanları
      • normal couple       -> ürüne bağlı CoupleProduct.design_id_1 / _2
    Yalnız kaleme bakmak normal couple'da hep BOŞ dönüyor ve "hangi yarı"
    sorusu yanlış cevaplanıyordu: paketlemede kalem hiç üretilmemiş sayılıyor,
    kalıptan yarı çıkarılırken YANLIŞ yarı hazır işaretleniyordu.

    Dönüş: (design_id_1, design_id_2) — str ya da None.
    """
    d1 = getattr(line_item, "assigned_design_id", None)
    d2 = getattr(line_item, "assigned_design_id_2", None)
    if (d1 is None or d2 is None) and getattr(line_item, "product_id", None) and db is not None:
        cp = db.scalar(select(CoupleProduct).where(
            CoupleProduct.product_id == str(line_item.product_id)))
        if cp is not None:
            if d1 is None:
                d1 = cp.design_id_1
            if d2 is None:
                d2 = cp.design_id_2
    return (str(d1) if d1 else None, str(d2) if d2 else None)


def couple_modelleri(line_item: LineItem) -> tuple[str, str]:
    """Couple kalemin IKI telefon modeli — elle girilen override'lar uygulanmis.

    Sipariş detayi, kalip ve paketleme AYNI modelleri gostermeli. Bu cozum
    tek yerde durmazsa ekranlar birbirinden ayrisir (paketlemede eski model,
    detayda elle duzeltilmis model gorunur).

    2. model yoksa 1. model tekrarlanir: cift kilif genelde ayni telefon icin.
    """
    pm1, pm2 = extract_couple_models(line_item)
    m1 = ((line_item.device_model_override or "").strip() or pm1
          or (extract_phone_model(line_item) or ""))
    m2 = (line_item.device_model_override_2 or "").strip() or pm2 or m1
    return m1, m2


def plan_molds(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    store_id: uuid.UUID | None = None,
    kodlari: pr.KalipKodlari | None = None,
) -> dict:
    """Kalıp planını hesapla.

    store_id verilirse o mağaza; None ise tenant'ın TÜM aktif mağazaları birleşik.
    """
    k = kodlari or pr.DEFAULT_KODLARI

    # Kişiye özel ürün id'leri (store_id, pid) ikilisi olarak
    kop_q = (
        select(KisiyeOzelProduct.store_id, KisiyeOzelProduct.product_id)
        .join(Store, Store.id == KisiyeOzelProduct.store_id)
        .where(
            Store.tenant_id == tenant_id,
            KisiyeOzelProduct.product_id.isnot(None),
        )
    )
    if store_id:
        kop_q = kop_q.where(KisiyeOzelProduct.store_id == store_id)
    kop_keys: set[tuple[uuid.UUID, str]] = {
        (s_id, str(pid)) for (s_id, pid) in db.execute(kop_q).all()
    }

    # Aksesuar (store_id, product_id) — kalip planina dahil edilmez
    acc_q = (
        select(AccessoryProduct.store_id, AccessoryProduct.product_id)
        .join(Store, Store.id == AccessoryProduct.store_id)
        .where(Store.tenant_id == tenant_id, AccessoryProduct.product_id.isnot(None))
    )
    if store_id:
        acc_q = acc_q.where(AccessoryProduct.store_id == store_id)
    acc_keys: set[tuple] = {(s_id, str(pid)) for (s_id, pid) in db.execute(acc_q).all()}

    # (store_id, product_id) -> Design
    design_q = (
        select(Design)
        .join(Store, Store.id == Design.store_id)
        .where(
            Store.tenant_id == tenant_id,
            Design.product_id.isnot(None),
        )
    )
    if store_id:
        design_q = design_q.where(Design.store_id == store_id)
    designs = db.scalars(design_q).all()
    # Iki seviyeli: (store, product, variant) varyant-ozel + (store, product, None) default
    design_by_key: dict[tuple, Design] = {}
    # Varyantlı ürünler: müşterinin property'den seçtiği değere (variant_title = match değeri)
    # göre tasarım. (store, product_id) -> [(match_norm, Design)]
    variant_designs: dict[tuple, list] = {}
    for d in designs:
        pid = str(d.product_id)
        vid = str(d.variant_id) if getattr(d, "variant_id", None) else None
        design_by_key[(d.store_id, pid, vid)] = d
        # variant'siz default: ilk gelen ya da variant_id None olan (None oncelikli)
        if vid is None or (d.store_id, pid, None) not in design_by_key:
            design_by_key[(d.store_id, pid, None)] = d
        _mv = (getattr(d, "variant_title", None) or "").strip()
        if _mv:
            variant_designs.setdefault((d.store_id, pid), []).append((_mv.casefold(), d))

    # Vitrin ürünleri: bağ product_id ile kurulamaz (UUID vs Shopify kimliği),
    # catalog_products.design_id'de ACIKCA tutulur. bkz. services/katalog_tasarim.py
    katalog_design = katalog_tasarim.bag_haritasi(db, tenant_id, store_id)

    # Couple (cift kilif) urunleri: (store_id, product_id) -> CoupleProduct
    couple_q = (
        select(CoupleProduct)
        .join(Store, Store.id == CoupleProduct.store_id)
        .where(Store.tenant_id == tenant_id, CoupleProduct.product_id.isnot(None))
    )
    if store_id:
        couple_q = couple_q.where(CoupleProduct.store_id == store_id)
    couple_rows = db.scalars(couple_q).all()
    couple_map: dict[tuple, CoupleProduct] = {
        (c.store_id, str(c.product_id)): c for c in couple_rows
    }
    # Couple tasarimlarini id'den bulmak icin (product_id'siz de olabilirler)
    _couple_design_ids = set()
    for c in couple_rows:
        if c.design_id_1: _couple_design_ids.add(c.design_id_1)
        if c.design_id_2: _couple_design_ids.add(c.design_id_2)
    design_by_id: dict[uuid.UUID, Design] = {}
    if _couple_design_ids:
        for d in db.scalars(select(Design).where(Design.id.in_(_couple_design_ids))).all():
            design_by_id[d.id] = d

    # Bekleyen siparişler
    #
    # ⚠ "AÇIK SİPARİŞ" TANIMI TEK KAYNAKTAN (services/order_scope). Burada
    # elle yazılmış bir kopya vardı ve `current_stage >= 8` ile `closed_at`
    # KONTROLLERİ EKSİKTİ. Sonuç 09.09.2026'da görüldü: #11677 kargoya
    # verilmişti ama Shopify'a fulfillment YAZILAMADIĞI için (HTTP 422,
    # "fulfillment order ... closed") `fulfillment_status` NULL kalmıştı.
    # Sipariş yerelde 8. aşamadaydı, plana göre ise hâlâ "açık". Kalem
    # 04.09'da elle kalıptan çıkarılıp plana döndürülünce (item_replan)
    # tek koruma olan `is_kaliba_eklendi` de sıfırlandı ve planlayıcı kalemi
    # yeni bir kalıba koydu — kılıf İKİNCİ KEZ basılıp çöpe gitti.
    # Kopya çıkarmayın: filtre değişecekse order_scope'ta değişir.
    from app.services.order_scope import acik_siparis_filtresi

    orders_q = (
        select(Order)
        .where(
            acik_siparis_filtresi(tenant_id),
            Order.kalip_haric == False,  # noqa: E712  kullanici kaliptan haric tuttu
            # Bayi portalinden gelen ama YONETICI ONAYLAMAMIS siparis kaliba
            # girmez: varyasyonu daha secilmedi ve cari borcu islenmedi.
            Order.bayii_onay_bekliyor == False,  # noqa: E712
        )
        .options(
            selectinload(Order.line_items).selectinload(LineItem.assigned_design),
            selectinload(Order.line_items).selectinload(LineItem.assigned_design_2),
        )
    )
    if store_id:
        orders_q = orders_q.where(Order.store_id == store_id)
    orders = db.scalars(orders_q).all()

    # --- ÇİFT PLANLAMA KORUMASI ---
    # is_kaliba_eklendi bayrağı sync sırasında Shopify line item id (external_id) ile
    # korunur; ancak Shopify'da sipariş DÜZENLENİRSE line item'lar YENİ id alır ve bayrak
    # kaybolur -> kalem TEKRAR planlanır (aynı ürün 2 kez kalıba girer). Bunu önlemek için
    # fiziksel MoldItem kayıtları source-of-truth: bu (sipariş, tasarım, model) zaten
    # kalıptaysa atla. ANAHTAR design_code DAHİL: aksi halde aynı modelden hâlâ kalıpta olan
    # kardeş ürün, geri planladığın FARKLI tasarımlı ürünü yanlışlıkla "kapsayıp" tekrar
    # planlanmasını engelliyordu.
    # BİRİNCİL ANAHTAR: line_item_id. Fiziksel slot hangi KALEME ait, doğrudan bu söyler.
    # Model/varyasyon/tasarım sonradan değişse bile kimlik değişmez -> koruma kör olmaz.
    # (Eski kayıtlarda bu bağ NULL olabilir; onlar için aşağıdaki üçlü anahtara düşülür.)
    from app.models import Mold as _Mold, MoldItem as _MoldItem
    from app.services.phone_models import normalize_key as _normkey
    _molded_by_li: dict = {}   # line_item_id -> mevcut fiziksel slot sayısı
    _molded_left: dict = {}    # (siparis, tasarim, model) -> sayı  [YALNIZCA bağı kopuk kayıtlar]
    _molded_by_slot: dict = {}  # (line_item_id, design_id) -> slot sayısı
    for _liid, _did, _on, _dc, _md in db.execute(
        select(_MoldItem.line_item_id, _MoldItem.design_id, _MoldItem.order_number,
               _MoldItem.design_code, _MoldItem.model)
        .join(_Mold, _Mold.id == _MoldItem.mold_id)
        .where(_Mold.tenant_id == tenant_id)
    ).all():
        if _liid:
            _molded_by_li[_liid] = _molded_by_li.get(_liid, 0) + 1
            # Çift kılıfta yarıları ayırt etmek için (kalem, tasarım) bazında da say.
            _molded_by_slot[(_liid, _did)] = _molded_by_slot.get((_liid, _did), 0) + 1
        elif _on and _md:
            _k = (str(_on), str(_dc or ""), _normkey(_md))
            _molded_left[_k] = _molded_left.get(_k, 0) + 1

    units: list[dict] = []
    # "liid|design_id" -> bu kalem+tasarim icin TOPLAM kac slot gerekli.
    # create_molds son savunmasi bunu kullanir: mevcut + planlanan > gerekli ise
    # gercekten cift baski riski var demektir. (Kalem bazinda bakmak yanlisti:
    # cift kilifin bir yarisi kaliptayken diger yariyi planlamak MESRU.)
    slot_ihtiyac: dict[str, int] = {}
    eksikler: list[dict] = []
    eksik_keys: set = set()

    # Eksik satırında "hangi bayinin hangi siparişi, hangi tasarım" görünsün:
    # eskiden yalnız kalem başlığı vardı; bayi kalemlerinin başlığı dosya adı
    # ("B9f61-260902154328-PDF2") olduğundan hangi siparişin eksik olduğu
    # anlaşılmıyordu.
    from app.models import Dealer as _Dealer
    _magaza_adlari = {
        s_.id: s_.name for s_ in db.scalars(
            select(Store).where(Store.tenant_id == tenant_id)).all()
    }
    _bayi_adlari = {
        str(d_.id): d_.name for d_ in db.scalars(
            select(_Dealer).where(_Dealer.tenant_id == tenant_id)).all()
    }

    def _bayi_adi(order) -> str | None:
        d_id = (order.raw or {}).get("dealer_id")
        return _bayi_adlari.get(str(d_id)) if d_id else None

    def add_eksik(reason, li, order, model, design=None):
        # Ürün kimliği olan kalemler (vitrin/Shopify) ürün bazında birleşir;
        # kimliği olmayanlar (bayi dosya yüklemeleri) kalem bazında KALIR —
        # yoksa farklı bayilerin kalemleri tek satıra gömülüyordu.
        ref = str(li.product_id) if li.product_id else f"li:{li.id}"
        key = (ref, reason)
        etiket = f"#{order.order_number}" + (f" · {_bayi_adi(order)}" if _bayi_adi(order) else "")
        tasarim = design or getattr(li, "assigned_design", None)
        if key in eksik_keys:
            for e in eksikler:
                if e["_ref"] == ref and e["reason"] == reason:
                    e["count"] += li.quantity or 1
                    if etiket not in e["siparisler"] and len(e["siparisler"]) < 8:
                        e["siparisler"].append(etiket)
                    return
        eksik_keys.add(key)
        eksikler.append({
            "_ref": ref,
            "reason": reason,
            "product_id": str(li.product_id) if li.product_id else None,
            "title": li.title,
            "model": model,
            "order_number": order.order_number,
            "order_id": str(order.id),
            "store_id": str(order.store_id),
            "magaza_adi": _magaza_adlari.get(order.store_id),
            "bayi_adi": _bayi_adi(order),
            "tasarim_kodu": getattr(tasarim, "code", None) if tasarim else None,
            "siparisler": [etiket],
            "count": li.quantity or 1,
        })

    for order in orders:
        order_store_id = order.store_id
        for li in (order.line_items or []):
            pid = str(li.product_id) if li.product_id else None
            # ★ ÜRÜN DEĞİŞİKLİĞİ BEKLİYOR ★ Müşteri başka ürün seçti ama tasarımı
            # henüz bağlanmadı: kalem ESKİ tasarımla basılmamalı.
            _ud = getattr(li, "urun_degisikligi", None) or {}
            if _ud.get("durum") == "bekliyor":
                add_eksik("urun_degisikligi_bekliyor", li, order, extract_phone_model(li))
                continue
            if pid and (order_store_id, pid) in acc_keys:
                continue  # aksesuar — kalipa da eksik listesine de girmez
            # Couple (cift kilif): 2 ayri tasarim, 2 birim — YARI BAZINDA ele alinir
            couple = couple_map.get((order_store_id, pid)) if pid else None

            if couple is None:
                # Tekil ürün: kalem bazında bayraklar geçerli
                if li.is_kaliba_eklendi or getattr(li, "is_hazir", False):
                    continue
                # ★ ÇİFT BASKI KORUMASI — BAYRAKTAN BAĞIMSIZ ★
                # Bu kalemin FİZİKSEL kalıp slotu varsa tekrar planlanamaz.
                if _molded_by_li.get(li.id, 0) > 0:
                    continue
            # Çift kılıfta 'hangi yarı ele alınmış' kontrolü, tasarımlar ÇÖZÜLDÜKTEN
            # sonra yapılır (aşağıda): kişiye özel olmayan couple'da tasarımlar
            # CoupleProduct'tan gelir, kalemin assigned_design_id'si BOŞTUR — buraya
            # bakmak "hiçbir yarı ele alınmamış" sonucu veriyor ve zaten kalıptaki
            # yarı ikinci kez planlanıyordu.
            model = extract_phone_model(li)

            if couple is not None:
                if couple.is_kisiye_ozel:
                    # Couple + kişiye özel: 2 tasarım sipariş başına yüklenir, modeller elle seçilir
                    d1 = li.assigned_design
                    d2 = li.assigned_design_2
                    if not d1 or not d2:
                        add_eksik("kisiye_ozel_tasarim_eksik", li, order, model)
                        continue
                    _m1 = (li.device_model_override or "").strip() or model
                    _m2 = (li.device_model_override_2 or "").strip() or _m1
                else:
                    d1 = design_by_id.get(couple.design_id_1) if couple.design_id_1 else None
                    d2 = design_by_id.get(couple.design_id_2) if couple.design_id_2 else None
                    if not d1 or not d2:
                        add_eksik("couple_tasarim_eksik", li, order, model)
                        continue
                    # Couple: 2 telefon modeli — model1=design_id_1, model2=design_id_2.
                    # ELLE DEĞİŞTİRİLEN model (override) property'yi EZER: müşteri modelini
                    # sonradan değiştirdiğinde üretim yeni modele göre yapılmalı.
                    _pm1, _pm2 = extract_couple_models(li)
                    _m1 = (li.device_model_override or "").strip() or _pm1 or model
                    _m2 = (li.device_model_override_2 or "").strip() or _pm2 or _m1
                if getattr(d1, "baski_dosyasi_yok", False) or getattr(d2, "baski_dosyasi_yok", False):
                    add_eksik("baski_dosyasi_yok", li, order, model)
                    continue
                if not _m1:
                    add_eksik("model_belirsiz", li, order, model)
                    continue
                qty = li.quantity or 1
                # ★ YARI BAZINDA İHTİYAÇ ★ Her yarı için kaç slot GEREKLİ, kaçı ZATEN VAR?
                # Anahtar GERÇEK slot tasarımı (d1/d2) — kişiye özel olmayan couple'da
                # bunlar CoupleProduct'tan gelir, kalemin assigned_design_id'si boştur.
                # Elle hazır işaretli yarı hiç planlanmaz.
                _ihtiyac: dict = {}
                for (_d, _slot_no) in ((d1, 1), (d2, 2)):
                    _manual = (getattr(li, "is_hazir", False) if _slot_no == 1
                               else getattr(li, "is_hazir_2", False))
                    if _manual or _d is None:
                        continue
                    _ihtiyac[_d.id] = _ihtiyac.get(_d.id, 0) + qty
                for _did in list(_ihtiyac):
                    slot_ihtiyac[f"{li.id}|{_did}"] = _ihtiyac[_did]
                    _ihtiyac[_did] = max(
                        0, _ihtiyac[_did] - _molded_by_slot.get((li.id, _did), 0))
                if not any(_ihtiyac.values()):
                    continue   # iki yarı da ele alınmış
                _ok = True
                _pending = []
                for (_cd, _cm, _slot) in ((d1, _m1, 1), (d2, _m2, 2)):
                    # Bu yarı için kalan ihtiyaç yoksa TEKRAR PLANLAMA — yoksa zaten
                    # kalıptaki yarı ikinci kez basılır.
                    _adet = _ihtiyac.get(_cd.id, 0) if _cd is not None else 0
                    if _adet <= 0:
                        continue
                    # Aynı tasarım iki yarıda da kullanılıyorsa ihtiyacı bir kez tüket
                    _ihtiyac[_cd.id] = 0
                    # Slot'a özel seçilen varyasyon > property > ürün adı > tasarımın kalip_tipi
                    _var = resolve_line_variation(li, _cd, slot=_slot)
                    if not _var:   # varyasyon yok -> SİYAH'a düşme, eksik olarak işaretle
                        add_eksik("varyasyon_eksik", li, order, _cm, _cd)
                        _ok = False
                        break
                    _var = pr.effective_variation(pr.get_model_group(_cm), _var)
                    _kod = pr.resolve_kalip_kodu(_cm, _var, k)
                    if not _kod:
                        add_eksik("model_taninmadi", li, order, _cm, _cd)
                        _ok = False
                        break
                    _pending.append((_cd, _var, _kod, _cm, _adet))
                if not _ok or not _pending:
                    continue
                for (_cd, _var, _kod, _cm, _adet) in _pending:
                    for _ in range(_adet):
                        units.append({
                            "line_item_id": str(li.id),
                            "order_id": str(order.id),
                            "order_number": order.order_number,
                            "store_id": str(order_store_id),
                            "model": _cm,
                            "product_id": pid,
                            "design_id": str(_cd.id),
                            "design_code": _cd.code,
                            "variation": _var,
                            "kod": _kod,
                            "satir_kod": pr.satir_kod(_kod, _cm),
                            "kilif_rengi": pr.kod_to_renk(_kod, _var),
                            "is_kisiye_ozel": False,
                            "title": li.title,
                            "thumbnail_url": (
                                storage.get_thumbnail_url(_cd.file_path, _cd.file_format)
                                if _cd else None
                            ),
                            "birincil_renk": getattr(_cd, "birincil_renk", None),
                            "kalip_tipi": getattr(_cd, "kalip_tipi", None),
                            "is_couple": True,
                            "is_telafi": bool(getattr(order, "is_telafi", False)),
                        })
                continue

            # Ürün değişikliği uygulandıysa kalem artık kişiye özel DEĞİL — Shopify
            # senkronu product_id'yi eski (kişiye özel) ürüne geri yazsa bile.
            is_ko = ((order_store_id, pid) in kop_keys if pid else False) and _ud.get("durum") != "uygulandi"

            design = None
            # 1) Manuel/bayii/kisiye ozel: tasarim dogrudan atanmissa onu kullan
            if li.assigned_design_id and li.assigned_design:
                design = li.assigned_design
            elif is_ko:
                # Kisiye ozel ama tasarim henuz yuklenmemis
                add_eksik("kisiye_ozel_tasarim_eksik", li, order, model)
                continue
            else:
                design = None
                # Varyantlı ürün: müşterinin property seçimine (variant_title=match) göre tasarım
                _matched_variant = False
                if pid:
                    _vl = variant_designs.get((order_store_id, pid))
                    if _vl:
                        _vd = match_variant_design(li, _vl)
                        if _vd is not None:
                            design = _vd
                            _matched_variant = True
                    if design is None:
                        _vid = str(li.variant_id) if getattr(li, "variant_id", None) else None
                        design = design_by_key.get((order_store_id, pid, _vid)) or design_by_key.get((order_store_id, pid, None))
                    if design is None:
                        # Vitrin ürünü: açık katalog bağı
                        design = katalog_design.get((order_store_id, pid))
                if design is None:
                    add_eksik("urun_tasarima_baglanmamis", li, order, model)
                    continue

            # Temiz baskı dosyası yok (hazır mockup/kılıflı görsel) -> kalıba girmesin
            if design is not None and getattr(design, "baski_dosyasi_yok", False):
                add_eksik("baski_dosyasi_yok", li, order, model, design)
                continue

            if not model:
                add_eksik("model_belirsiz", li, order, model, design)
                continue

            # Kılıf varyasyonu önceliği:
            # 1) Eşleşen varyant tasarımı varsa ONUN kalip_tipi'si
            # 2) Line item'a özel seçilen kılıf varyasyonu (kişiye özel panelde ŞEFFAF vb.)
            # 3) Müşteri property'den varyasyon seçtiyse o
            # 4) Tasarımın kalip_tipi'si (varsayılan)
            if locals().get("_matched_variant"):
                # Varyantlı ürün: müşteri hangi varyantı seçtiyse ONUN tasarımının
                # kalip_tipi'si belirleyicidir (eşleşme zaten varyanttan geldi).
                _dkt = ((design.kalip_tipi or "").strip() if design else "")
                variation = pr.normalize_variation(_dkt) if _dkt else None
            else:
                variation = resolve_line_variation(li, design, slot=1)
            # Hiçbir kaynakta varyasyon yoksa SESSİZCE SİYAH'a düşme — eksik olarak işaretle
            # (yanlış varyasyonla kalıba girip hatalı üretim olmasın).
            if not variation:
                add_eksik("varyasyon_eksik", li, order, model, design)
                continue
            variation = pr.effective_variation(pr.get_model_group(model), variation)
            kod = pr.resolve_kalip_kodu(model, variation, k)
            if not kod:
                add_eksik("model_taninmadi", li, order, model, design)
                continue

            qty = li.quantity or 1

            # Çift planlama koruması: bu (sipariş, tasarım, model) zaten kalıp(lar)da tam
            # adetiyle varsa (is_kaliba_eklendi bayrağı Shopify düzenlemesiyle kaybolsa bile)
            # tekrar planlama. design_code dahil olduğu için, geri planladığın farklı tasarımlı
            # kalemler aynı modeldeki kardeşler tarafından yanlışlıkla "kapsanmaz".
            _onum = str(order.order_number) if order.order_number is not None else None
            _mk = (_onum, str(design.code or ""), _normkey(model)) if _onum else None
            if _mk and _molded_left.get(_mk, 0) >= qty:
                _molded_left[_mk] -= qty
                continue
            slot_ihtiyac[f"{li.id}|{design.id}"] = qty

            for _ in range(qty):
                units.append({
                    "line_item_id": str(li.id),
                    "order_id": str(order.id),
                    "order_number": order.order_number,
                    "store_id": str(order_store_id),
                    "model": model,
                    "product_id": pid,
                    "design_id": str(design.id),
                    "design_code": design.code,
                    "variation": variation,
                    "kod": kod,
                    "satir_kod": pr.satir_kod(kod, model),
                    "kilif_rengi": pr.kod_to_renk(kod, variation),
                    "is_kisiye_ozel": is_ko,
                    "title": li.title,
                    "thumbnail_url": (
                        storage.get_thumbnail_url(design.file_path, design.file_format)
                        if design else None
                    ),
                    "birincil_renk": getattr(design, "birincil_renk", None),
                    "kalip_tipi": getattr(design, "kalip_tipi", None),
                    "is_telafi": bool(getattr(order, "is_telafi", False)),
                })

    # (satir_kod, variation) grupla, 27 üstü parçala. Özel varyasyonlar (SEFFAF/
    # PARLAK/MAGSAFE) satir_kod ile gruba bölünür -> farklı boyutlar ayrı satıra;
    # gerçek kod ("SEFFAF") display/kısa kod için korunur.
    groups: dict[tuple, list[dict]] = {}
    for u in units:
        groups.setdefault((u["satir_kod"], u["variation"]), []).append(u)

    queue: list[dict] = []
    for (_skod, variation), items in groups.items():
        real_kod = items[0]["kod"]  # gerçek kalıp kodu (kısa kod/display için)
        for i in range(0, len(items), pr.KALIP_MAX_BOXES):
            chunk = items[i:i + pr.KALIP_MAX_BOXES]
            queue.append({
                "items": chunk,
                "count": len(chunk),
                "variation": variation,
                "kodlar": [real_kod],
                "is_merged": False,
            })

    packed = pr.bin_pack_by_variation(queue)

    def sort_key(b):
        var_idx = pr.VARIATIONS.index(b["variation"]) if b["variation"] in pr.VARIATIONS else 99
        first_kod = sorted(b["kodlar"], key=lambda c: pr.kod_to_group_priority(c, k))[0]
        return (var_idx, pr.kod_to_group_priority(first_kod, k))

    packed.sort(key=sort_key)

    molds = []
    for idx, b in enumerate(packed, 1):
        kod_counts: dict[str, int] = {}
        line_item_ids: set = set()
        store_ids_in_mold: set = set()
        for it in b["items"]:
            kod_counts[it["kod"]] = kod_counts.get(it["kod"], 0) + 1
            line_item_ids.add(it["line_item_id"])
            if it.get("store_id"):
                store_ids_in_mold.add(it["store_id"])
        # İÇERİK İMZASI: kalıbın hangi kalemlerden oluştuğunu belirler. Plan her
        # istekte yeniden hesaplandığı için sıra numarası güvenilir değil; kullanıcı
        # "şunu oluştur" derken bu imzayı gönderir, içerik değiştiyse eşleşmez.
        _imza = hashlib.sha1(
            "|".join(sorted(line_item_ids)).encode("utf-8")
        ).hexdigest()[:12]
        molds.append({
            "imza": _imza,
            "sira": idx,
            "variation": b["variation"],
            "kodlar": sorted(b["kodlar"], key=lambda c: pr.kod_to_group_priority(c, k)),
            "kod_counts": kod_counts,
            "count": b["count"],
            "rows_used": pr._count_rows(b["items"]),
            "is_merged": b["is_merged"],
            "is_multi_store": len(store_ids_in_mold) > 1,
            "store_ids": sorted(store_ids_in_mold),
            "line_item_ids": sorted(line_item_ids),
            "items": [
                {
                    "kod": it["kod"],
                    "satir_kod": it.get("satir_kod", it["kod"]),
                    "design_code": it["design_code"],
                    "model": it["model"],
                    "order_number": it["order_number"],
                    "variation": it["variation"],
                    "kilif_rengi": pr.kod_to_renk(it["kod"], it["variation"]),
                    "is_kisiye_ozel": it["is_kisiye_ozel"],
                    "line_item_id": it["line_item_id"],
                    "design_id": it["design_id"],
                    "store_id": it.get("store_id"),
                    "thumbnail_url": it.get("thumbnail_url"),
                    "birincil_renk": it.get("birincil_renk"),
                    "kalip_tipi": it.get("kalip_tipi"),
                }
                for it in b["items"]
            ],
        })

    # ── Askı kontrolü: plandaki kalemler dükkanda hazır bekleyen (askı) ürünle
    # eşleşiyor mu? Eşleşiyorsa yeniden basmaya gerek olmayabilir — operatöre uyar.
    # (design_id + model; model normalize edilir ki '15' ile 'iPhone 15' örtüşsün.)
    aski_uyarilar = []
    try:
        from app.models import AskiItem as _Aski
        from app.services import phone_models as _pm
        aski_rows = db.scalars(select(_Aski).where(
            _Aski.tenant_id == tenant_id, _Aski.quantity > 0)).all()
        if aski_rows and units:
            aski_stock: dict = {}
            for a in aski_rows:
                key = (str(a.store_id), str(a.design_id), _pm.normalize_key(a.model or ""))
                aski_stock[key] = aski_stock.get(key, 0) + (a.quantity or 0)
            demand: dict = {}
            for u in units:
                if not u.get("design_id"):
                    continue
                key = (str(u.get("store_id")), str(u["design_id"]), _pm.normalize_key(u.get("model") or ""))
                if key not in aski_stock:
                    continue
                d = demand.setdefault(key, {
                    "design_code": u.get("design_code"),
                    "model": _pm.canonical_model_name(u.get("model") or ""),
                    "adet": 0, "siparisler": set(),
                })
                d["adet"] += 1
                if u.get("order_number"):
                    d["siparisler"].add(str(u["order_number"]))
            for key, d in demand.items():
                mevcut = aski_stock.get(key, 0)
                aski_uyarilar.append({
                    "design_code": d["design_code"],
                    "model": d["model"],
                    "aski_mevcut": mevcut,
                    "plandaki_adet": d["adet"],
                    "karsilanabilir": min(mevcut, d["adet"]),
                    "siparisler": sorted(d["siparisler"]),
                })
            aski_uyarilar.sort(key=lambda x: -x["karsilanabilir"])
    except Exception:  # noqa: BLE001
        aski_uyarilar = []

    # ── BOŞ KILIF STOĞU: plan basılmadan ÖNCE yetiyor mu? ────────────────
    # ⚠ NEDEN: stok eksikliği bugüne kadar ancak baskı anında ya da fiziksel
    # olarak fark ediliyordu — kalem kalıptan çıkarılıyor, müşteriye "ürününüz
    # yok" mesajı gidiyor. Canlıda ayda ~113 kalem kalıptan çıkarılıyor,
    # ağustosta 38'i stok yüzündendi. Stok verisi ZATEN var (255 kalem,
    # baskıda deduct_for_mold ile düşülüyor); planlayıcı ona hiç bakmıyordu.
    #
    # UYARIDIR, ENGEL DEĞİL: stok sayımı her zaman güncel olmayabilir ve
    # operatör "elimde var" diyip basabilmeli. Karar onun.
    stok_uyarilar = []
    try:
        from app.services import stock as _stok

        # (varyasyon, model) başına kaç adet gerekiyor
        ihtiyac: dict = {}
        for u in units:
            anahtar = (u.get("variation") or "", u.get("model") or "")
            d = ihtiyac.setdefault(anahtar, {"adet": 0, "siparisler": set()})
            d["adet"] += 1
            if u.get("order_number"):
                d["siparisler"].add(str(u["order_number"]))

        for (varyasyon, model), d in ihtiyac.items():
            if not model:
                continue
            si = _stok._find_bos_kilif(db, tenant_id, varyasyon, model)
            # Stok kaydı HİÇ yoksa uyarı vermiyoruz: her model tanımlı değil ve
            # "tanımsız" ile "bitmiş" farklı şeyler. Yanlış alarm, gerçek
            # alarmı da değersizleştirir.
            if si is None:
                continue
            mevcut = si.quantity or 0
            if mevcut >= d["adet"]:
                continue
            stok_uyarilar.append({
                "model": model,
                "variation": varyasyon,
                "gerekli": d["adet"],
                "mevcut": mevcut,
                "eksik": d["adet"] - mevcut,
                "siparisler": sorted(d["siparisler"]),
            })
        stok_uyarilar.sort(key=lambda x: -x["eksik"])
    except Exception:  # noqa: BLE001 — stok bakılamazsa plan YİNE üretilsin
        stok_uyarilar = []

    return {
        "molds": molds,
        "slot_ihtiyac": slot_ihtiyac,
        "stok_uyarilar": stok_uyarilar,
        "stok_eksik_toplam": sum(x["eksik"] for x in stok_uyarilar),
        "mold_count": len(molds),
        "total_units": len(units),
        "eksikler": eksikler,
        "eksik_count": sum(e["count"] for e in eksikler),
        "can_create": len(eksikler) == 0 and len(molds) > 0,
        "aski_uyarilar": aski_uyarilar,
        "aski_uyari_count": sum(u["karsilanabilir"] for u in aski_uyarilar),
        "stats": {
            "kalip_sayisi": len(molds),
            "toplam_kilif": len(units),
            "eksik_kalem": sum(e["count"] for e in eksikler),
        },
    }
