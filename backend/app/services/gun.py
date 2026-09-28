"""Gün sınırları — TEK KAYNAK: Europe/Istanbul.

⚠ NEDEN VAR: dashboard "bugün"ü `date.today()` ile alıp UTC gece yarısı
sayıyordu, analitik de aralığı UTC ile kuruyordu. Canlı sunucu İstanbul
saatinde olduğu için "bugün" İstanbul 03:00'te başlıyordu: 00:00–03:00 arası
gelen siparişler dashboard ve analitikte DÜNE yazılıyordu. Günlük grafikte de
gruplama veritabanı oturumunun saat dilimine kalıyordu (canlıda İstanbul,
CI'da UTC — aynı kod iki yerde farklı gün veriyordu).

İş İstanbul'da; kullanıcı "bugün"ü İstanbul günü olarak düşünür. Günle ilgili
her hesap buradan geçmeli.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func

TR = ZoneInfo("Europe/Istanbul")
TR_ADI = "Europe/Istanbul"


def bugun(simdi: datetime | None = None) -> date:
    """İstanbul'a göre bugünün tarihi (sunucunun saat diliminden bağımsız)."""
    return (simdi or datetime.now(timezone.utc)).astimezone(TR).date()


def gun_basi(gun: date) -> datetime:
    """İstanbul günü 00:00 → UTC an (timestamptz karşılaştırması için)."""
    return datetime.combine(gun, time.min, tzinfo=TR).astimezone(timezone.utc)


def aralik(bas: date, bit: date) -> tuple[datetime, datetime]:
    """[bas, bit] İstanbul günleri (iki uç dahil) → (başlangıç, bitiş HARİÇ) UTC."""
    return gun_basi(bas), gun_basi(bit + timedelta(days=1))


def gun_sql(kolon):
    """SQL: timestamptz kolonun İSTANBUL günü (date_trunc) — gruplamada
    veritabanı oturumunun saat dilimine güvenilmez."""
    return func.date_trunc("day", func.timezone(TR_ADI, kolon))
