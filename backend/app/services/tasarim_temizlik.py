"""Kargolanan siparişlerin JPG/PNG tasarım dosyalarını 48 saat sonra sil.

NEDEN: bayiler aynı görseli tekrar tekrar yüklüyor ve ham JPG/PNG'ler diskte
birikiyor. Sipariş kargoya verildikten sonra baskı dosyasına ihtiyaç kalmıyor.

GÜVENLİK KURALLARI — hiçbiri gevşetilmemeli, yanlış silme yanlış/boş baskı
demektir:
  1) Yalnız JPG/JPEG/PNG. PDF (baskıya hazır dosya) ASLA silinmez.
  2) Tasarımın BAĞLI OLDUĞU HER sipariş kargolanmış olmalı (aşama >= 8) ve
     hepsinin üzerinden 48 saat geçmiş olmalı. Tek bir sipariş bile üretimde
     ise dosyaya DOKUNULMAZ.
  3) Tasarım hiçbir FİZİKSEL KALIP slotunda olmamalı.
  4) Hiç siparişe bağlı olmayan tasarıma dokunulmaz (bayinin katalogda
     bekleyen tasarımı olabilir).
  5) SİLİNMİŞ sipariş (çöp kutusu) engel SAYILMAZ — ama yalnız silinmesinin
     üzerinden de 48 saat geçtiyse. Çöpten geri alma penceresi içinde dosya
     durur; yoksa geri alınan siparişin tasarımı yok olurdu. Bu kural olmadan
     silinmiş sipariş dosyayı SONSUZA DEK tutuyordu (aşaması < 8 kaldığı için
     "hepsi kargolanmış" koşulu asla sağlanmıyordu).
Kayıt SİLİNMEZ, yalnız dosya silinir ve `dosya_silindi_at` işaretlenir; sipariş
geçmişi bozulmaz. İşaretli tasarım katalogda GÖRÜNMEZ (seçilemez).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Design
from app.services import storage

logger = logging.getLogger("tasarim-temizlik")

SILINEBILIR_FORMAT = ("jpg", "jpeg", "png")
BEKLEME_SAAT = 48
KARGO_ASAMASI = 8


def adaylari_bul(db: Session, saat: int = BEKLEME_SAAT) -> list[Design]:
    """Silinebilir tasarımlar. Kurallar modül başlığında."""
    sinir = datetime.now(UTC) - timedelta(hours=saat)
    sql = text("""
        select d.id
          from designs d
         where d.dosya_silindi_at is null
           and lower(d.file_format) = any(:formatlar)
           -- en az bir siparişe bağlı olmalı
           and exists (select 1 from line_items l where l.assigned_design_id = d.id)
           -- HİÇBİR kalıp slotunda olmamalı
           and not exists (select 1 from mold_items m where m.design_id = d.id)
           -- bağlı olduğu HER sipariş kargolanmış ve üstünden 48 saat geçmiş
           -- olmalı. Kargo zamanı durum GEÇMİŞİNDEN okunur (orders'ta böyle
           -- bir alan yok); "kargoya_verildi" kaydı tam o an yazılıyor.
           and not exists (
                 select 1 from line_items l join orders o on o.id = l.order_id
                  where l.assigned_design_id = d.id
                    -- 48 saatten once silinmis siparis engel degil (kural 5)
                    and (o.deleted_at is null or o.deleted_at > :sinir)
                    and (coalesce(o.current_stage, 1) < :asama
                         or not exists (
                              select 1 from order_status_history h
                               where h.order_id = o.id
                                 and h.action = 'kargoya_verildi'
                                 and h.created_at <= :sinir)))
    """)
    idler = [r[0] for r in db.execute(sql, {
        "formatlar": list(SILINEBILIR_FORMAT), "asama": KARGO_ASAMASI, "sinir": sinir})]
    if not idler:
        return []
    return list(db.scalars(select(Design).where(Design.id.in_(idler))).all())


def calistir(db: Session, saat: int = BEKLEME_SAAT, kuru: bool = False) -> dict:
    """Temizliği uygula. kuru=True ise HİÇBİR ŞEY SİLMEZ, yalnız raporlar."""
    adaylar = adaylari_bul(db, saat)
    silinen, bayt = 0, 0
    kodlar: list[str] = []
    for d in adaylar:
        bayt += int(d.file_size_bytes or 0)
        kodlar.append(d.code)
        if kuru:
            continue
        storage.delete_design_file(d.file_path)
        d.dosya_silindi_at = datetime.now(UTC)
        silinen += 1
    if not kuru and silinen:
        db.commit()
        logger.info("[tasarim-temizlik] %s dosya silindi (%.1f MB): %s",
                    silinen, bayt / 1048576, ", ".join(kodlar[:20]))
    return {"aday": len(adaylar), "silinen": silinen,
            "mb": round(bayt / 1048576, 2), "kodlar": kodlar[:50], "kuru": kuru}
