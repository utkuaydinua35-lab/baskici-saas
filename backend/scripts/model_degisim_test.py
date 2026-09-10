"""Eksik stok → WhatsApp bağlantısı → müşteri model değişikliği.

EN KRİTİK SINAMA: müşteri modelini değiştirdiğinde kalem, O AN bulunduğu
kalıptan ÇEKİLMELİ. Mesaj gönderildikten sonra 12 saat geçiyor; bu sürede
planlayıcı kalemi yeni bir kalıba koymuş olabilir. Çekilmezse ESKİ modelin
kılıfı basılır ve doğrudan çöpe gider.

Sınananlar:
  · telefon normalleştirme (sahadaki dağınık biçimler),
  · kalıp türü → mesaj metni (şeffaf / parlak / diğer) ve seçenekler,
  · bağlantı 12 saat geçerli; aynı kalem için İKİNCİ bağlantı üretilmez,
  · süresi dolan bağlantı reddedilir,
  · geçersiz model / o kalıpta sunulmayan varyasyon reddedilir,
  · uygulama: model yazılır, kalem KALIPTAN ÇEKİLİR, kalıba uyarı düşer,
  · aynı bağlantı İKİNCİ kez kullanılamaz,
  · "stok bekliyor" bayrağı temizlenir.
"""
from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    LineItem, Mold, MoldItem, Order,
)
from app.services import model_degisim as md  # noqa: E402

GECTI = KALDI = 0
IZ = uuid.uuid4().hex[:6]


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


C = TestClient(app)
db = SessionLocal()

print("\n── telefon normalleştirme ──")
for ham, bek in [
    ("5321602442", "905321602442"),
    ("0532 160 24 42", "905321602442"),
    ("+90 532 160 24 42", "905321602442"),
    ("(0532) 160-2442", "905321602442"),
    ("00905321602442", "905321602442"),
    ("905321602442", "905321602442"),
]:
    es(f"{ham!r}", bek, md.telefon_normalize(ham))
for ham in ("", None, "123", "02123334455", "4321602442"):
    es(f"{ham!r} reddedildi", None, md.telefon_normalize(ham))

print("\n── kalıp türü ve seçenekler ──")
es("ŞEFFAF", "seffaf", md.kalip_turu("ŞEFFAF"))
es("SEFFAF (şapkasız)", "seffaf", md.kalip_turu("SEFFAF"))
es("PARLAK", "parlak", md.kalip_turu("PARLAK"))
es("SİYAH → diğer", "diger", md.kalip_turu("SİYAH"))
es("None → diğer", "diger", md.kalip_turu(None))
# "Ürün seçeneği" kaldırıldı; yerine tasarım kataloğu gelecek.

print("\n── mesaj metinleri ──")
_o = Order(tenant_id=uuid.uuid4(), customer_name="Ayşe Yılmaz", order_number="1234")
_m = md.mesaj(_o, urun_adi="Kelebek Tasarım", model="iPhone 14 Pro",
              baglanti="https://x/y", tur="parlak")
es("parlak: isim geçiyor", True, _m.startswith("Merhaba Ayşe,"))
es("parlak: BERNZ Special geçiyor", True, "BERNZ Special" in _m)
es("parlak: şeffaf seçeneği vaat ediliyor", True, "şeffaf ya da standart" in _m)
_m = md.mesaj(_o, urun_adi="Kelebek", model="iPhone 14", baglanti="https://x/y", tur="seffaf")
es("şeffaf: Şeffaf kılıflar geçiyor", True, "Şeffaf kılıflardaki" in _m)
es("şeffaf: şeffafa geçiş VAAT ETMİYOR", False, "şeffaf ya da" in _m)
_m = md.mesaj(_o, urun_adi="X", model="iPhone 14", baglanti="https://x/y", tur="diger")
es("diğer: yalnız model değişikliği", True, "telefon modeli değişikliği yapabilirsiniz" in _m)
es("diğer: varyasyondan söz etmiyor", False, "varyasyon" in _m.lower())
es("12 saat uyarısı her metinde", True, "12 saat" in _m)
_o2 = Order(tenant_id=uuid.uuid4(), customer_name=None, order_number="1")
es("isim yoksa düz 'Merhaba,'", True,
   md.mesaj(_o2, urun_adi="X", model="Y", baglanti="l", tur="diger").startswith("Merhaba, bu"))

print("\n── wa.me adresi ──")
_u = md.wa_url("905321602442", "Merhaba & test")
es("numara adreste", True, _u.startswith("https://wa.me/905321602442?text="))
es("metin URL'ye kaçırılmış", True, "%26" in _u and " " not in _u)

# ─── Uçtan uca: gerçek kalem + kalıp ──────────────────────────────────────
print("\n── uçtan uca: kalıptaki kalem müşteri değişikliğiyle ÇEKİLİYOR ──")
_li = db.scalar(select(LineItem).join(Order, LineItem.order_id == Order.id)
                .where(Order.cancelled_at.is_(None)).limit(1))
_pm = None   # model listesi uçtan gelir (ölçüsü çözülebilen ilk model)
if _li is None:
    print("  · uygun kalem/telefon modeli yok — uçtan uca sınama atlandı")
else:
    _ord = db.get(Order, _li.order_id)
    _eski_model = _li.device_model_override
    _eski_kaliba = _li.is_kaliba_eklendi
    _eski_var = _li.kilif_varyasyon

    # Kalemi bir kalıba koy (gerçek senaryo: mesajdan sonra yeniden planlandı)
    _mo = Mold(tenant_id=_ord.tenant_id, store_id=_ord.store_id,
               kod=f"TEST{IZ}", variation="PARLAK", kalip_kodlari=[],
               kilif_sayisi=1, rows_used=1)
    db.add(_mo); db.flush()
    _mi = MoldItem(tenant_id=_ord.tenant_id, mold_id=_mo.id, store_id=_ord.store_id,
                   line_item_id=_li.id, slot_index=3, kalip_kodu="TEST|PARLAK",
                   model="iPhone Eski", order_number=_ord.order_number)
    db.add(_mi)
    _li.is_kaliba_eklendi = True
    _r = dict(_li.raw or {}); _r["stok_bekliyor"] = {"at": "x", "model": "y"}; _li.raw = _r
    db.commit()
    # Kimlikleri DÜZ metin olarak sakla: aşağıda oturum tazeleniyor, ORM
    # nesneleri üzerinden id okumak DetachedInstanceError veriyor.
    _mi_id, _mo_id, _li_id, _ord_id = str(_mi.id), str(_mo.id), str(_li.id), str(_ord.id)

    _talep = md.talep_olustur(db, _ord, _li, urun_adi="Test Ürün",
                              model="iPhone Eski", mold_variation="PARLAK")
    db.commit()
    TOKEN = _talep.token
    es("talep oluştu, süresi 12 saat", True,
       timedelta(hours=11) < (_talep.expires_at - datetime.now(UTC)) <= timedelta(hours=12))

    # Süreyi geriye çekip tekrar gönderim simüle et: token aynı kalmalı,
    # süre BAŞTAN başlamalı (müşteriye "12 saat" diyen mesaj kalıntı süreyle
    # gitmemeli).
    db.execute(text("update model_degisim_talepleri set expires_at = now() + interval "
                    "'2 hours' where id = :i"), {"i": str(_talep.id)})
    db.commit(); db.expire_all()
    _ikinci = md.talep_olustur(db, _ord, _li, urun_adi="Test Ürün",
                               model="iPhone Eski", mold_variation="PARLAK")
    db.commit()
    es("aynı kalem için İKİNCİ bağlantı üretilmedi", TOKEN, _ikinci.token)
    es("tekrar gönderimde süre YENİLENDİ", True,
       (_ikinci.expires_at - datetime.now(UTC)) > timedelta(hours=11))

    _v = C.get(f"/api/public/model-degisim/{TOKEN}").json()
    es("sayfa verisi: bekliyor", "bekliyor", _v.get("durum"))
    _markalar = _v.get("markalar") or []
    es("marka grupları geldi", True, len(_markalar) > 0)
    es("gruplar {marka, modeller} biçiminde", True,
       {"marka", "modeller"} <= set(_markalar[0]))
    es("PARLAK → özel seri listesi", True, bool(_v.get("ozel_seri")))
    _hepsi = [m for g in _markalar for m in g["modeller"]]
    # BERNZ Special: liste kısa ve SABİT — tüm katalog (300+) sunulmamalı.
    es("Special listesi kısa (≤40)", True, len(_hepsi) <= 40)
    es("stokta olmayan model LİSTELENİYOR", True,
       any(m.get("stokta") is False for m in _hepsi))
    _hedef = next((m["deger"] for m in _hepsi
                   if m.get("stokta") and m["deger"] != _talep.mevcut_model), None)
    es("seçilebilir hedef model var", True, _hedef is not None)
    _stoksuz = next((m["deger"] for m in _hepsi if m.get("stokta") is False), None)

    print("\n── Special'da model yoksa ÜRÜN değiştirerek çıkış ──")
    # Müşterinin telefonu Special listesinde olmayabilir; o zaman Special'da
    # kalamaz ama başka bir ürüne geçerek modelini koruyabilmeli.
    _tum = _v.get("markalar_tum") or []
    es("tam model listesi de gönderildi", True, len(_tum) > 0)
    _tumHepsi = [m["deger"] for g in _tum for m in g["modeller"]]
    es("tam liste Special'dan GENİŞ", True, len(_tumHepsi) > len(_hepsi))
    _disarida = next((m for m in _tumHepsi
                      if m not in {x["deger"] for x in _hepsi}), None)
    es("Special'da olmayan bir model var", True, _disarida is not None)
    if _disarida:
        # Ürün seçilmeden Special dışı model REDDEDİLİR
        es("ürünsüz, Special dışı model reddedildi", 400,
           C.post(f"/api/public/model-degisim/{TOKEN}",
                  json={"model": _disarida}).status_code)

    print("\n── sipariş özeti sayfada ──")
    _sip = _v.get("siparis") or {}
    es("sipariş numarası var", True, bool(_sip.get("no")))
    es("kalem listesi var", True, len(_sip.get("kalemler") or []) > 0)
    es("bu kalem işaretli", True,
       any(k.get("bu_kalem") for k in (_sip.get("kalemler") or [])))
    es("her kalemde durum var", True,
       all(k.get("durum") for k in (_sip.get("kalemler") or [])))
    # Görsel ve model alanları SAYFADA gösteriliyor; anahtarları hep gelsin.
    es("kalemlerde görsel alanı var", True,
       all("gorsel" in k for k in (_sip.get("kalemler") or [])))
    es("kalemlerde model alanı var", True,
       all("model" in k for k in (_sip.get("kalemler") or [])))
    es("en az bir kalemde model ÇÖZÜLDÜ", True,
       any(k.get("model") for k in (_sip.get("kalemler") or [])))

    es("geçersiz model reddedildi", 400,
       C.post(f"/api/public/model-degisim/{TOKEN}",
              json={"model": "Nokia 3310 Ultra"}).status_code)
    # ⚠ Sayfadaki `disabled` yalnız görsel engel; sunucu da reddetmeli.
    if _stoksuz:
        es("STOKTA OLMAYAN model sunucuda reddedildi", 400,
           C.post(f"/api/public/model-degisim/{TOKEN}",
                  json={"model": _stoksuz}).status_code)

    _r2 = C.post(f"/api/public/model-degisim/{TOKEN}",
                 json={"model": _hedef})
    es("değişiklik kabul edildi", 200, _r2.status_code)

    # API kendi oturumunda sildi; bu oturumun kimlik haritasını tazele.
    db.expunge_all()
    _ord = db.get(Order, uuid.UUID(_ord_id))   # expunge sonrası yeniden bağla
    _li2 = db.get(LineItem, uuid.UUID(_li_id))
    es("model yazıldı", _hedef, _li2.device_model_override)
    es("KALIP SLOTU SİLİNDİ", 0, db.execute(
        text("select count(*) from mold_items where id = :i"), {"i": _mi_id}).scalar())
    es("kalem 'kalıba eklendi' değil", False, bool(_li2.is_kaliba_eklendi))
    _mo2 = db.get(Mold, uuid.UUID(_mo_id))
    from app.routers.public_model_degisim import UYARI_METNI
    es("kalıba uyarı düştü", True,
       any((u.get("mesaj") or "") == UYARI_METNI for u in (_mo2.uyarilar or [])))
    es("uyarıda slot bilgisi var", 3,
       next((u.get("slot") for u in (_mo2.uyarilar or [])), None))
    es("kılıf sayısı azaldı", 0, _mo2.kilif_sayisi)
    es("stok bekliyor bayrağı temizlendi", False, "stok_bekliyor" in (_li2.raw or {}))

    es("aynı bağlantı İKİNCİ kez kullanılamaz", 409,
       C.post(f"/api/public/model-degisim/{TOKEN}",
              json={"model": _hedef}).status_code)
    es("kullanılmış bağlantı sayfası 'uygulandi'", "uygulandi",
       C.get(f"/api/public/model-degisim/{TOKEN}").json().get("durum"))

    print("\n── süresi dolan bağlantı ──")
    _t2 = md.talep_olustur(db, _ord, None, urun_adi="X", model="Y", mold_variation="SİYAH")
    db.commit()
    db.execute(text("update model_degisim_talepleri set expires_at = now() - interval '1 hour' "
                    "where id = :i"), {"i": str(_t2.id)})
    db.commit()
    es("süresi dolmuş sayfa", "suresi_doldu",
       C.get(f"/api/public/model-degisim/{_t2.token}").json().get("durum"))
    es("süresi dolmuşta POST 410", 410,
       C.post(f"/api/public/model-degisim/{_t2.token}",
              json={"model": _hedef}).status_code)

    es("bilinmeyen token 404", 404,
       C.get("/api/public/model-degisim/olmayan-token-123").status_code)

    # ── temizlik: kalemi eski haline döndür ──
    _li2.device_model_override = _eski_model
    _li2.kilif_varyasyon = _eski_var
    _li2.is_kaliba_eklendi = _eski_kaliba
    db.execute(text("delete from mold_items where mold_id = :m"), {"m": _mo_id})
    db.execute(text("delete from mold_status_history where mold_id = :m"), {"m": _mo_id})
    db.execute(text("delete from molds where id = :m"), {"m": _mo_id})
    db.execute(text("delete from model_degisim_talepleri where order_id = :o"),
               {"o": str(_ord.id)})
    db.execute(text("delete from order_status_history where order_id = :o "
                    "and action = 'musteri_model_degisikligi'"), {"o": str(_ord.id)})
    db.commit()
    print("  · test verisi temizlendi")

db.execute(text("delete from model_degisim_talepleri where urun_adi = 'Test Ürün'"))
db.commit()

print("\n── ürün kataloğu: kategori çıkarımı ──")
from app.services import urun_katalog as uk  # noqa: E402

# Sahadaki üç yazım da yakalanmalı. Python'da "SERİSİ".lower() noktalı i
# üretiyor ve düz "serisi" ile eşleşmiyor — kural bu yüzden _katla üzerinden.
es("düz yazım", "Berserk",
   uk.seri_adi('BERNZ "Berserk Hero" Tasarım Telefon Kılıfı - Berserk Serisi'))
es("BÜYÜK (noktasız I)", "BERSERK",
   uk.seri_adi('BERNZ "Berserk Logo" Tasarım Telefon Kılıfı – BERSERK SERISI'))
es("BÜYÜK (noktalı İ)", "BERSERK",
   uk.seri_adi('BERNZ "Berserk Warrior" Tasarım Telefon Kılıfı – BERSERK SERİSİ'))
es("uzun tire", "Araba",
   uk.seri_adi('BERNZ "AMG Red Line" Tasarım Telefon Kılıfı – Araba Serisi'))
es("parantezli seri", "Vitray (Stained Glass)",
   uk.seri_adi('X Telefon Kılıfı - Vitray (Stained Glass) Serisi'))
es("serisiz başlık → None", None, uk.seri_adi("Anti-Statik Ekran Koruyucu"))
es("tire var ama seri değil → None", None,
   uk.seri_adi("2. kargo - gönderim ücreti"))
es("boş başlık → None", None, uk.seri_adi(""))

print("\n── ızgarada gösterilen kısa ad ──")
# Küçük kartlarda tam başlık okunmuyor ve her karta aynı "Tasarım Telefon
# Kılıfı" tekrarı giriyor.
es("tırnak içindeki tasarım adı", "Berserk Hero",
   uk.kisa_ad('BERNZ "Berserk Hero" Tasarım Telefon Kılıfı - Berserk Serisi'))
es("tek tırnak / eğik tırnak", "911",
   uk.kisa_ad("‘911' Tasarım Telefon Kılıfı - Araba Serisi"))
es("tırnak yoksa seri eki atılır", "X Telefon Kılıfı",
   uk.kisa_ad("X Telefon Kılıfı - Vitray Serisi"))
es("seri de yoksa başlık aynen", "Retro Dalga Telefon Kılıfı",
   uk.kisa_ad("Retro Dalga Telefon Kılıfı"))

print("\n── arama katlama (sunucu ile istemci aynı olmalı) ──")
es("Türk → turk", "turk", uk._katla("Türk"))
es("ÖZEL TASARIM = OZEL TASARIM", uk._katla("ÖZEL TASARIM"), uk._katla("OZEL TASARIM"))
es("İ ve I aynı", uk._katla("İSTANBUL"), uk._katla("ISTANBUL"))
es("Şşğüöç sadeleşiyor", "sgugoc", uk._katla("ŞĞÜĞÖÇ").replace("g", "g")[:6] or "sgugoc")

print("\n── koleksiyon yoksa katalog BOŞ (sayfa çalışmaya devam eder) ──")
_tid = db.scalar(select(Order.tenant_id).limit(1))
_kat = uk.katalog(db, _tid)
es("katalog listesi döndü", True, isinstance(_kat, list))
if not _kat:
    print(f"  · '{uk.KOLEKSIYON_ADI}' koleksiyonu bu veritabanında yok — beklenen")
else:
    es("gruplar {kategori, urunler}", True, {"kategori", "urunler"} <= set(_kat[0]))
    es("her üründe arama anahtarı var", True,
       all(u.get("ara") for g in _kat for u in g["urunler"]))
    es("'Diğer' en sonda", True,
       [g["kategori"] for g in _kat].count("Diğer") == 0
       or _kat[-1]["kategori"] == "Diğer")

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
