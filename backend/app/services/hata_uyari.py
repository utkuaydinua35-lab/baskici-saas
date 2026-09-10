"""Yakalanmayan sunucu hatalarını HABER VER — Telegram + platform bildirimi.

⚠ NEDEN VAR: bir uçta beklenmeyen bir istisna olduğunda hiçbir yere haber
gitmiyordu; yalnız log dosyasına düşüyordu ve o dosyayı kimse okumuyordu.
Yani bir müşteri sayfası patlasa, müşteri şikayet edene kadar haberimiz olmazdı.

TASARIM KARARLARI:
  · AYNI HATA SPAM YAPMAZ. Bir döngü hataya girerse dakikada yüzlerce mesaj
    gelir ve kanal kullanılamaz hale gelir; bildirim susturulmuş olur. Hata
    PARMAK İZİNE göre gruplanıp aynı iz için 15 dakikada bir uyarı çıkar,
    araya sıkışan sayı da mesajda yazılır.
  · Uyarı gönderimi İSTEĞİ BOZMAZ. Uyarıda hata çıkarsa yutulur — aksi halde
    "hata bildirimi" hatanın kendisinden beter olurdu.
  · Gövde/başlık İÇERİĞİ gönderilmez: müşteri adresi, e-posta, token
    taşıyabilir. Yalnız yol, yöntem, hata türü ve yığın izinin son satırları.
"""
from __future__ import annotations

import hashlib
import logging
import time
import traceback

logger = logging.getLogger("hata")

_SON: dict[str, float] = {}
_SAYAC: dict[str, int] = {}
BEKLEME = 900          # aynı parmak izi için 15 dk
_AZAMI_IZ = 2000       # bellekte tutulan farklı hata sayısı


def _parmak_izi(yol: str, exc: BaseException) -> str:
    """Aynı hata = aynı uç + aynı istisna türü + yığının SON karesi.

    Mesaj metnini karıştırmıyoruz: içinde değişen id/sayı olur ve her seferinde
    yeni bir iz üretip susturmayı işe yaramaz hale getirirdi.
    """
    kare = ""
    iz = traceback.extract_tb(exc.__traceback__)
    if iz:
        son = iz[-1]
        kare = f"{son.filename}:{son.lineno}"
    ham = f"{yol}|{type(exc).__name__}|{kare}"
    return hashlib.sha256(ham.encode()).hexdigest()[:16]


def _budala() -> None:
    if len(_SON) <= _AZAMI_IZ:
        return
    simdi = time.time()
    for k in [k for k, v in _SON.items() if simdi - v > BEKLEME * 4]:
        _SON.pop(k, None)
        _SAYAC.pop(k, None)


def bildir(yontem: str, yol: str, exc: BaseException) -> bool:
    """Hatayı uyarı kanallarına düşür. Gönderildiyse True.

    ASLA istisna yükseltmez.
    """
    try:
        iz = _parmak_izi(yol, exc)
        simdi = time.time()
        _SAYAC[iz] = _SAYAC.get(iz, 0) + 1
        if simdi - _SON.get(iz, 0) < BEKLEME:
            return False          # susturuldu; sayaç birikiyor
        tekrar = _SAYAC.pop(iz, 1)
        _SON[iz] = simdi
        _budala()

        satirlar = traceback.format_exception(type(exc), exc, exc.__traceback__)
        # Yığının SONU asıl hatanın olduğu yer; başı çerçeve gürültüsü.
        kuyruk = "".join(satirlar)[-900:]
        ek = f" · son 15 dk'da {tekrar} kez" if tekrar > 1 else ""

        from app.services import telegram
        telegram.send_message(
            f"🐞 <b>Sunucu hatası</b>{ek}\n"
            f"<code>{yontem} {yol}</code>\n"
            f"<b>{type(exc).__name__}</b>: {str(exc)[:200]}\n"
            f"<pre>{kuyruk[-700:]}</pre>"
        )
        try:
            from app.services import push
            from app.database import SessionLocal
            with SessionLocal() as db:
                push.send_to_platform_admins(
                    db, "🐞 Sunucu hatası",
                    f"{yontem} {yol} · {type(exc).__name__}",
                    url="/platform", tag=f"hata-{iz}")
        except Exception:  # noqa: BLE001 — push yoksa Telegram yeter
            pass
        return True
    except Exception as e:  # noqa: BLE001 — uyarı, isteği ASLA bozmaz
        logger.warning(f"[hata] uyarı gönderilemedi: {e}")
        return False
