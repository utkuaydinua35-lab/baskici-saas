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

from dataclasses import dataclass
from datetime import date, datetime, timezone

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
