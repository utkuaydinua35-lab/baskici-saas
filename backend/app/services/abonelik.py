"""Kiralama aboneliği — plan erişimi ve ödeme durumu için TEK kaynak.

İKİ AYRI SORU CEVAPLANIR
─────────────────────────
1. Kiracı NEYE erişebilir?   → plana göre modüller → panel yetkileri
2. Kiracı ŞU AN ne yapabilir? → ödeme durumuna göre (tam / salt-okunur / askıda)

Bu ikisi bilinçli olarak ayrı: Pro planlı ama ödemesi gecikmiş bir kiracı
üretim modülünü GÖREBİLİR ama hiçbir şey DEĞİŞTİREMEZ.

ÖDEME GECİKMESİ — KADEMELİ
───────────────────────────
active_until, ödenmiş son gündür. Ondan sonra:

    gün 1-7    ek_sure      her şey açık, panelde uyarı bandı
    gün 8-14   salt_okunur  panel yalnız okunur, vitrin AÇIK
    gün 15+    askida       panel yalnız okunur, vitrin BAKIMDA

Kiracının müşterilerine karşı adil (vitrin iki hafta daha satış yapar), ama
ödeme baskısı kurar. is_active=False ise tarihten bağımsız doğrudan askıda.

PLATFORM YÖNETİCİSİ HİÇBİR ZAMAN KISITLANMAZ
─────────────────────────────────────────────
Sahibin kendi kullanıcısı (is_platform_admin) plan kısıtına takılmaz. Bu bir
güvenlik supabıdır: "sahip" planı yanlışlıkla silinirse ya da bir kiracıya
atanırsa, sahip kendi atölyesine kilitlenip kalmaz.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from app.auth.permissions import ALL_PERMISSIONS

EK_SURE_GUN = 7
VITRIN_KAPANMA_GUN = 14

# Modül → açtığı panel yetkileri.
#
# `magaza` her planda vardır: vitrin + mağaza paneli (sipariş, ürün, müşteri,
# kupon, tema, pazarlama). Mağaza panelinin çağırdığı uçların istediği yetkiler
# (vitrin, siparisler, musteri, dashboard, pazarlama) bunun içinde — Basic
# planlı bir kiracı sipariş gönderemez hâle düşmesin diye kodla doğrulandı.
MODUL_YETKILERI: dict[str, frozenset[str]] = {
    "magaza": frozenset({
        "dashboard", "siparisler", "destek", "ayarlar", "kullanici_yonetimi",
        "pazarlama", "vitrin", "musteri",
    }),
    "tasarim_studyosu": frozenset({"tasarim", "kisiye_ozel"}),
    "uretim": frozenset({
        "paketleme", "aksesuar", "couple", "kalip", "stok", "telefon_modelleri",
    }),
    "bayi": frozenset({"bayii", "bayii_portal"}),
}

MODUL_ADLARI = {
    "magaza": "Vitrin + mağaza paneli",
    "tasarim_studyosu": "Tasarım stüdyosu",
    "uretim": "Baskı / üretim paneli",
    "bayi": "Bayi portalı",
}

# Her yetki TAM OLARAK bir modüle ait olmalı. Yeni bir yetki eklenip bir
# modüle bağlanmazsa HİÇBİR planda açılmaz ve sessizce herkesten gizlenir —
# bunu modül yüklenirken yakalıyoruz, üretimde değil.
_tum = frozenset().union(*MODUL_YETKILERI.values())
assert _tum == frozenset(ALL_PERMISSIONS), (
    "Modüle bağlanmamış yetki var: "
    f"{sorted(set(ALL_PERMISSIONS) - _tum)} / fazladan: {sorted(_tum - set(ALL_PERMISSIONS))}"
)
_kesisim = [(a, b) for a in MODUL_YETKILERI for b in MODUL_YETKILERI
            if a < b and MODUL_YETKILERI[a] & MODUL_YETKILERI[b]]
assert not _kesisim, f"Bir yetki iki modülde birden: {_kesisim}"

# Plansız kiracı (yeni kayıt, plan atanmamış) EN KISITLI hâle düşer.
# Tersi — plansızı sınırsız saymak — tehlikeli: plan atamayı unutmak,
# kiracıya üretim ve bayi modüllerini bedavaya açmak demek olurdu.
VARSAYILAN_MODULLER = ("magaza",)


def plan_modulleri(tenant) -> tuple[str, ...]:
    plan = getattr(tenant, "plan_kaydi", None)
    if plan is None:
        return VARSAYILAN_MODULLER
    return tuple(m for m in (plan.moduller or []) if m in MODUL_YETKILERI)


def izinli_yetkiler(tenant) -> frozenset[str]:
    """Kiracının PLANININ açtığı panel yetkileri (kullanıcı yetkisinden ayrı)."""
    return frozenset().union(*(MODUL_YETKILERI[m] for m in plan_modulleri(tenant)))


@dataclass(frozen=True)
class Durum:
    asama: str            # aktif | ek_sure | salt_okunur | askida
    yazma_izni: bool
    vitrin_acik: bool
    kalan_gun: int | None  # bir sonraki aşamaya kaç gün (None = süresiz)
    mesaj: str | None

    def sozluk(self) -> dict:
        return {"asama": self.asama, "yazma_izni": self.yazma_izni,
                "vitrin_acik": self.vitrin_acik, "kalan_gun": self.kalan_gun,
                "mesaj": self.mesaj}


def _bugun() -> date:
    return datetime.now(timezone.utc).date()


def durum(tenant, bugun: date | None = None) -> Durum:
    """Kiracının ödeme durumu. Tarihe dayalı, saf fonksiyon — test edilebilir."""
    if tenant is None:
        return Durum("askida", False, False, None, "Hesap bulunamadı.")
    if not getattr(tenant, "is_active", True):
        return Durum("askida", False, False, None,
                     "Hesabınız askıya alındı. Lütfen bizimle iletişime geçin.")

    bitis = getattr(tenant, "active_until", None)
    if bitis is None:
        return Durum("aktif", True, True, None, None)

    bugun = bugun or _bugun()
    gecen = (bugun - bitis).days

    if gecen <= 0:
        kalan = -gecen
        # Bitişe 5 gün kala nazik bir hatırlatma
        mesaj = (f"Aboneliğiniz {kalan} gün sonra yenilenmeli."
                 if kalan <= 5 else None)
        return Durum("aktif", True, True, kalan, mesaj)
    if gecen <= EK_SURE_GUN:
        kalan = EK_SURE_GUN - gecen
        return Durum("ek_sure", True, True, kalan,
                     f"Aboneliğinizin süresi doldu. {kalan} gün içinde ödeme "
                     f"yapılmazsa panel salt-okunur olacak.")
    if gecen <= VITRIN_KAPANMA_GUN:
        kalan = VITRIN_KAPANMA_GUN - gecen
        return Durum("salt_okunur", False, True, kalan,
                     f"Ödeme yapılmadığı için panel salt-okunur. {kalan} gün "
                     f"içinde ödeme yapılmazsa vitrininiz kapanacak.")
    return Durum("askida", False, False, None,
                 "Ödeme yapılmadığı için vitrininiz kapatıldı. Ödeme yapıldığında "
                 "her şey kaldığı yerden devam eder.")


# ─── Tahakkuk ve ödeme (Faz 3) ──────────────────────────────────────────────
#
# FATURA DÜZENİ — Shopify faturasıyla aynı:
#   • Sabit ücret PEŞİN: ödeme, active_until'ın ertesi gününden başlayan yeni
#     dönemi (ay_sayisi ay) kapsar.
#   • Komisyon GEÇEN dönemin satışından: son ödemenin kapsadığı satış gününün
#     ertesinden yeni dönemin bir önceki gününe kadar. Zincirleme olduğu için
#     hiçbir gün iki kez sayılmaz, hiçbir gün atlanmaz.
#
# KOMİSYON MATRAHI (karar: 2026-09-27, "Shopify'da nasılsa öyle"):
#   Yalnız VİTRİN satışları (Store.platform == "storefront"); Shopify, bayi,
#   elle girilen sipariş komisyona girmez. Tutar sipariş toplamı: indirim
#   düşülmüş, KDV + kargo DAHİL — Shopify'ın üçüncü taraf işlem ücretiyle aynı
#   matrah. Bilinçli fark: Shopify iade edilen siparişin ücretini geri vermez;
#   biz telafi / iptal / tam iadeyi DÜŞERİZ, çünkü panel ciroyu böyle sayıyor
#   ve kiracının gördüğü ciro ile faturası birebir tutmalı.


def ay_ekle(gun: date, ay: int) -> date:
    """Takvim ayı ekle/çıkar; hedef ayda o gün yoksa ayın son günü
    (31 Ocak + 1 ay = 28/29 Şubat)."""
    yil_farki, ay0 = divmod(gun.month - 1 + ay, 12)
    yil, ay_no = gun.year + yil_farki, ay0 + 1
    return date(yil, ay_no, min(gun.day, calendar.monthrange(yil, ay_no)[1]))


def vitrin_cirosu(db, tenant_id, bas: date, bit: date) -> tuple[Decimal, int]:
    """[bas, bit] (iki uç dahil) vitrin satışı: (TL tutar, sipariş adedi).

    Gün sınırları analitik ekranıyla aynı (UTC) — kiracının panelde gördüğü
    ciro ile faturadaki birebir tutsun.
    """
    from sqlalchemy import func, select

    from app.models import Order, Store
    from app.services import ciro

    bas_dt = datetime.combine(bas, time.min, tzinfo=timezone.utc)
    bit_dt = datetime.combine(bit + timedelta(days=1), time.min, tzinfo=timezone.utc)
    tutar, adet = db.execute(
        select(func.coalesce(func.sum(ciro.tl_tutar()), 0), func.count(Order.id))
        .join(Store, Store.id == Order.store_id)
        .where(
            Order.tenant_id == tenant_id,
            Store.platform == "storefront",
            Order.is_telafi.is_(False),
            Order.cancelled_at.is_(None),
            (Order.financial_status != "refunded") | (Order.financial_status.is_(None)),
            Order.created_at_platform >= bas_dt,
            Order.created_at_platform < bit_dt,
        )
    ).one()
    return Decimal(str(tutar or 0)).quantize(Decimal("0.01")), int(adet or 0)


@dataclass(frozen=True)
class Tahakkuk:
    plan_id: object
    plan_ad: str
    ay_sayisi: int
    donem_bas: date
    donem_bit: date
    sabit_ucret: Decimal
    ciro_bas: date | None
    ciro_bit: date | None
    ciro: Decimal
    siparis_sayisi: int
    komisyon_orani: Decimal
    komisyon: Decimal
    toplam: Decimal
    onceki_bitis: date | None
    yeni_bitis: date

    def sozluk(self) -> dict:
        def s(v):
            if isinstance(v, date):
                return v.isoformat()
            if isinstance(v, Decimal):
                return str(v)
            return v
        return {k: s(getattr(self, k)) for k in self.__dataclass_fields__
                if k != "plan_id"} | {"plan_id": str(self.plan_id)}


def _son_odeme(db, tenant_id):
    from sqlalchemy import select

    from app.models import AbonelikOdemesi
    # Sıra yeni_bitis'e göre: her ödeme aboneliği İLERİ taşır, zincirin sonu
    # en ileri tarihtir. created_at'e güvenilmez — aynı işlemde yazılan iki
    # kayıtta eşit çıkar ve "en son" belirsizleşir (test yakaladı).
    return db.scalar(
        select(AbonelikOdemesi)
        .where(AbonelikOdemesi.tenant_id == tenant_id, AbonelikOdemesi.durum == "odendi")
        .order_by(AbonelikOdemesi.yeni_bitis.desc().nullslast(),
                  AbonelikOdemesi.created_at.desc()).limit(1)
    )


def tahakkuk_hesapla(db, tenant, ay_sayisi: int = 1, bugun: date | None = None) -> Tahakkuk:
    """Şimdi ödeme alınsa ne kadar tutar, hangi dönemi kapsar — kaydetmez."""
    plan = getattr(tenant, "plan_kaydi", None)
    if plan is None:
        raise ValueError("Kiracıya plan atanmamış — önce plan seçin.")
    if not 1 <= ay_sayisi <= 24:
        raise ValueError("Ay sayısı 1-24 arasında olmalı.")
    bugun = bugun or _bugun()
    bitis = tenant.active_until

    # Yeni dönemin başı. Vitrini kapanmamış kiracı kaldığı yerden devam eder
    # (ek süre ve salt-okunur günlerinde hizmeti kullandı); vitrini kapanmış
    # ya da hiç bitiş tarihi olmayan kiracı BUGÜNDEN başlar — kapalı kaldığı
    # günlerin ücreti alınmaz.
    if bitis is None or (bugun - bitis).days > VITRIN_KAPANMA_GUN:
        donem_bas = bugun
    else:
        donem_bas = bitis + timedelta(days=1)
    donem_bit = ay_ekle(donem_bas, ay_sayisi) - timedelta(days=1)

    # Komisyon dönemi — zincirin devamı
    son = _son_odeme(db, tenant.id)
    if son is not None and son.ciro_bit is not None:
        ciro_bas = son.ciro_bit + timedelta(days=1)
    elif son is not None:
        ciro_bas = son.donem_bas
    elif bitis is not None:
        ciro_bas = ay_ekle(bitis, -1) + timedelta(days=1)
    else:
        # İlk ödeme ve bitiş tarihi yok: kiracı şimdiye kadar süresiz
        # (sınırsız plan / deneme) kullandı. Komisyon ilk ücretli dönemle
        # başlar — sınırsızdan ücretliye geçen kiracıdan YILLARIN cirosu
        # üzerinden komisyon kesilmesin.
        ciro_bas = None
    ciro_bit = donem_bas - timedelta(days=1)
    if ciro_bas is not None and ciro_bas > ciro_bit:
        ciro_bas = None

    if ciro_bas is None:
        ciro_tutar, adet, ciro_bit_kayit = Decimal("0.00"), 0, None
    else:
        ciro_tutar, adet = vitrin_cirosu(db, tenant.id, ciro_bas, ciro_bit)
        ciro_bit_kayit = ciro_bit

    oran = Decimal(str(plan.komisyon_orani or 0))
    komisyon = (ciro_tutar * oran / Decimal(100)).quantize(Decimal("0.01"), ROUND_HALF_UP)
    sabit = (Decimal(str(plan.aylik_ucret or 0)) * ay_sayisi).quantize(Decimal("0.01"))
    return Tahakkuk(
        plan_id=plan.id, plan_ad=plan.ad, ay_sayisi=ay_sayisi,
        donem_bas=donem_bas, donem_bit=donem_bit, sabit_ucret=sabit,
        ciro_bas=ciro_bas, ciro_bit=ciro_bit_kayit, ciro=ciro_tutar,
        siparis_sayisi=adet, komisyon_orani=oran, komisyon=komisyon,
        toplam=sabit + komisyon, onceki_bitis=bitis, yeni_bitis=donem_bit,
    )


def odeme_kaydet(db, tenant, *, yontem: str, ay_sayisi: int = 1,
                 referans: str | None = None, not_: str | None = None,
                 fatura_no: str | None = None,
                 kaydeden_id=None, bugun: date | None = None):
    """Ödemeyi kaydet ve aboneliği uzat. Tutarlar o anın plan fiyatıyla
    dondurulur. Commit ÇAĞIRANIN işi."""
    from app.models import AbonelikOdemesi

    if yontem not in ("havale", "kart"):
        raise ValueError("Geçersiz ödeme yöntemi.")
    t = tahakkuk_hesapla(db, tenant, ay_sayisi, bugun)
    odeme = AbonelikOdemesi(
        tenant_id=tenant.id, plan_id=t.plan_id,
        donem_bas=t.donem_bas, donem_bit=t.donem_bit, ay_sayisi=t.ay_sayisi,
        sabit_ucret=t.sabit_ucret, ciro=t.ciro, ciro_bas=t.ciro_bas, ciro_bit=t.ciro_bit,
        siparis_sayisi=t.siparis_sayisi, komisyon_orani=t.komisyon_orani,
        komisyon=t.komisyon, toplam=t.toplam, yontem=yontem, durum="odendi",
        referans=(referans or "").strip()[:200] or None,
        not_=(not_ or "").strip()[:2000] or None,
        fatura_no=(fatura_no or "").strip()[:60] or None,
        odendi_at=datetime.now(timezone.utc), created_by=kaydeden_id,
        onceki_bitis=t.onceki_bitis, yeni_bitis=t.yeni_bitis,
    )
    db.add(odeme)
    tenant.active_until = t.yeni_bitis
    return odeme


def odeme_iptal(db, odeme) -> None:
    """Yanlış girilen ödemeyi geri al: kayıt 'iptal' olur, abonelik bitişi
    ödemeden önceki tarihe döner. Yalnız EN SON ödeme iptal edilebilir —
    araya başka ödeme girdiyse tarihleri geri sarmak zinciri bozar."""
    from app.models import Tenant

    if odeme.durum != "odendi":
        raise ValueError("Bu kayıt zaten iptal edilmiş.")
    son = _son_odeme(db, odeme.tenant_id)
    if son is None or son.id != odeme.id:
        raise ValueError("Yalnız en son ödeme iptal edilebilir; önce sonrakileri iptal edin.")
    tenant = db.get(Tenant, odeme.tenant_id)
    # Bitiş o arada elle değiştirildiyse ona dokunma — yöneticinin kararı
    if tenant is not None and tenant.active_until == odeme.yeni_bitis:
        tenant.active_until = odeme.onceki_bitis
    odeme.durum = "iptal"


# ─── Havale bilgileri (platform ayarı) ─────────────────────────────────────

HAVALE_ALANLARI = {"alici": 120, "banka": 80, "iban": 34, "aciklama": 300}


def havale_bilgisi(db) -> dict:
    """Kiracılara gösterilen havale bilgileri (platform_ayarlari["havale"])."""
    from app.models import PlatformAyari

    kayit = db.get(PlatformAyari, "havale")
    deger = (kayit.deger if kayit else None) or {}
    return {k: str(deger.get(k) or "") for k in HAVALE_ALANLARI}


# ─── Kartla ödeme (Faz 4) ──────────────────────────────────────────────────
#
# Kiracı "Kartla öde" der → tahakkuk o an DONDURULUP "bekliyor" kaydı açılır
# → iyzico ödeme sayfası → iyzico onaylarsa kayıt "odendi" olur ve abonelik
# uzar. Tutar başlatırken dondurulur: müşteri iyzico sayfasındayken yeni bir
# sipariş düşse de çekilen tutar gördüğü tutarla aynı kalır.

KART_INCELEME_NOTU = ("⚠ İnceleme: ödeme sırasında aboneliğe başka bir ödeme işlendi; "
                      "dönem ödeme anına göre yeniden hesaplandı, komisyon dönemi "
                      "çakışıyor olabilir.")


def kart_odemesi_hazirla(db, tenant, *, ay_sayisi: int, beklenen_toplam: Decimal,
                         kaydeden_id=None, bugun: date | None = None):
    """Bekleyen kart ödemesi kaydı. Önizlemedeki tutar değiştiyse ValueError
    (kiracı görmediği tutarı ödemesin). Commit ÇAĞIRANIN işi."""
    from app.models import AbonelikOdemesi

    t = tahakkuk_hesapla(db, tenant, ay_sayisi, bugun)
    if t.toplam != Decimal(str(beklenen_toplam)).quantize(Decimal("0.01")):
        raise ValueError(f"Tutar değişti: güncel toplam {t.toplam} TL. Sayfayı yenileyin.")
    if t.toplam <= 0:
        raise ValueError("Ödenecek tutar yok.")
    kayit = AbonelikOdemesi(
        tenant_id=tenant.id, plan_id=t.plan_id,
        donem_bas=t.donem_bas, donem_bit=t.donem_bit, ay_sayisi=t.ay_sayisi,
        sabit_ucret=t.sabit_ucret, ciro=t.ciro, ciro_bas=t.ciro_bas, ciro_bit=t.ciro_bit,
        siparis_sayisi=t.siparis_sayisi, komisyon_orani=t.komisyon_orani,
        komisyon=t.komisyon, toplam=t.toplam, yontem="kart", durum="bekliyor",
        created_by=kaydeden_id, onceki_bitis=t.onceki_bitis, yeni_bitis=t.yeni_bitis,
    )
    db.add(kayit)
    return kayit


def kart_odemesini_tamamla(db, kayit, *, saglayici_ref: str,
                           bugun: date | None = None) -> bool:
    """iyzico ödemeyi ONAYLADIKTAN sonra: kaydı ödendi yap, aboneliği uzat.

    Tekrar çağrılırsa (tarayıcı geri dönüşü iki kez) hiçbir şey yapmaz.
    Dönüş: kayıt tutarlı mı. False ise ödeme yine işlenir — para çekildi,
    kiracının hakkı verilir — ama kayıt inceleme notu alır ve yönetici uyarılmalı.
    Commit ÇAĞIRANIN işi.
    """
    from app.models import Tenant

    if kayit.durum == "odendi":
        return True
    tenant = db.get(Tenant, kayit.tenant_id)
    tutarli = kayit.durum == "bekliyor" and tenant.active_until == kayit.onceki_bitis
    if not tutarli:
        # Arada başka ödeme işlendi (ya da kayıt vazgeçildi sayılmıştı):
        # dönemi ŞİMDİKİ duruma göre yeniden kur, ödenen tutar aynen kalır.
        bugun = bugun or _bugun()
        bitis = tenant.active_until
        if bitis is None or (bugun - bitis).days > VITRIN_KAPANMA_GUN:
            donem_bas = bugun
        else:
            donem_bas = bitis + timedelta(days=1)
        kayit.donem_bas = donem_bas
        kayit.donem_bit = ay_ekle(donem_bas, kayit.ay_sayisi) - timedelta(days=1)
        kayit.onceki_bitis = bitis
        kayit.yeni_bitis = kayit.donem_bit
        kayit.not_ = ((kayit.not_ or "") + "\n" + KART_INCELEME_NOTU).strip()
    kayit.durum = "odendi"
    kayit.referans = (saglayici_ref or "")[:200] or None
    kayit.odendi_at = datetime.now(timezone.utc)
    tenant.active_until = kayit.yeni_bitis
    return tutarli
