"""Cihazlar arası geçici dosya aktarımı.

Kalıcı depo DEĞİL: yüklenen her dosya 24 saat sonra silinir (scheduler).
Amaç bir dosyayı bir cihazdan diğerine hızlıca taşımak; sunucuda yer
kaplamaması şart.

TASARIM NOTLARI
  • Dosya diske PARÇA PARÇA yazılır — 250 MB'lık bir dosyayı belleğe almak
    2 worker'lı sunucuda belleği şişirir (bkz. VPS balonu notu).
  • Boyut sınırı YAZARKEN denetlenir: Content-Length başlığına güvenmek
    yanlış, istemci yalan söyleyebilir. Sınır aşılınca yarım dosya silinir.
  • Dosya adı KULLANILMAZ: diskteki ad rastgele bir token + uzantı. Böylece
    çakışma, yol kaçışı (../) ve asıl adın sızması derdi yok.
"""
from __future__ import annotations

import secrets
import uuid as _uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DosyaAktarimi
from app.services.uploads import UPLOAD_ROOT

AKTARIM_DIR = UPLOAD_ROOT / "aktarim"
MAX_BOYUT = 250 * 1024 * 1024          # 250 MB
SAKLAMA_SAAT = 24
PARCA = 1024 * 1024                    # 1 MB'lık parçalarla yaz


def _uzanti(ad: str) -> str:
    son = Path(ad or "").suffix.lower()
    # Nokta + en fazla 10 harf/rakam; başka her şey atılır (uzantı dosya
    # adından geliyor, güvenilmez)
    if 2 <= len(son) <= 11 and son[1:].isalnum():
        return son
    return ""


def boyut_yaz(bayt: int) -> str:
    mb = bayt / 1024 / 1024
    if mb >= 1:
        return f"{mb:.1f} MB"
    return f"{max(1, bayt // 1024)} KB"


def kaydet(db: Session, *, tenant_id, user, dosya) -> DosyaAktarimi:
    """UploadFile'ı diske yaz ve kaydı oluştur. Sınır aşılırsa ValueError."""
    AKTARIM_DIR.mkdir(parents=True, exist_ok=True)
    ad = (getattr(dosya, "filename", "") or "dosya").strip()[:300]
    hedef_ad = f"{secrets.token_hex(16)}{_uzanti(ad)}"
    hedef = AKTARIM_DIR / hedef_ad
    toplam = 0
    try:
        with open(hedef, "wb") as f:
            while True:
                parca = dosya.file.read(PARCA)
                if not parca:
                    break
                toplam += len(parca)
                if toplam > MAX_BOYUT:
                    raise ValueError(
                        f"Dosya çok büyük — en fazla {MAX_BOYUT // 1024 // 1024} MB")
                f.write(parca)
    except Exception:
        hedef.unlink(missing_ok=True)      # yarım dosya kalmasın
        raise
    if toplam == 0:
        hedef.unlink(missing_ok=True)
        raise ValueError("Boş dosya")

    kayit = DosyaAktarimi(
        tenant_id=tenant_id,
        user_id=getattr(user, "id", None),
        yukleyen=(getattr(user, "full_name", None) or getattr(user, "email", None)),
        dosya_adi=ad,
        yol=f"aktarim/{hedef_ad}",
        boyut=toplam,
        tur=(getattr(dosya, "content_type", None) or None),
        expires_at=datetime.now(UTC) + timedelta(hours=SAKLAMA_SAAT),
    )
    db.add(kayit)
    db.flush()
    return kayit


def tam_yol(kayit: DosyaAktarimi) -> Path:
    return UPLOAD_ROOT / kayit.yol


def listele(db: Session, tenant_id) -> list[DosyaAktarimi]:
    """Süresi DOLMAMIŞ kayıtlar, yeniden eskiye.

    Süresi geçmişler listede hiç görünmez — temizlik işi henüz koşmamış olsa
    bile kullanıcı ölü bağlantıya tıklamasın.
    """
    simdi = datetime.now(UTC)
    return list(db.scalars(
        select(DosyaAktarimi)
        .where(DosyaAktarimi.tenant_id == tenant_id, DosyaAktarimi.expires_at > simdi)
        .order_by(DosyaAktarimi.created_at.desc())
    ).all())


def bul(db: Session, tenant_id, kayit_id: _uuid.UUID) -> DosyaAktarimi | None:
    return db.scalar(select(DosyaAktarimi).where(
        DosyaAktarimi.id == kayit_id, DosyaAktarimi.tenant_id == tenant_id))


def sil(db: Session, kayit: DosyaAktarimi) -> None:
    tam_yol(kayit).unlink(missing_ok=True)
    db.delete(kayit)


def temizle(db: Session) -> dict:
    """Süresi dolmuş kayıtları ve dosyalarını sil. Scheduler saatte bir çağırır.

    Ayrıca KAYITSIZ dosyaları da süpürür: yükleme yarıda kalıp kayıt
    oluşmazsa dosya diskte öksüz kalır ve kimse fark etmez.
    """
    simdi = datetime.now(UTC)
    silinen = 0
    bayt = 0
    for k in db.scalars(select(DosyaAktarimi).where(DosyaAktarimi.expires_at <= simdi)).all():
        bayt += k.boyut or 0
        sil(db, k)
        silinen += 1
    db.commit()

    oksuz = 0
    if AKTARIM_DIR.exists():
        bilinen = {Path(y).name for (y,) in db.execute(select(DosyaAktarimi.yol)).all()}
        esik = simdi.timestamp() - SAKLAMA_SAAT * 3600
        for p in AKTARIM_DIR.iterdir():
            if p.is_file() and p.name not in bilinen and p.stat().st_mtime < esik:
                p.unlink(missing_ok=True)
                oksuz += 1
    return {"silinen": silinen, "mb": round(bayt / 1024 / 1024, 1), "oksuz": oksuz}
