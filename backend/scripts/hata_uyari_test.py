"""Yakalanmayan sunucu hatası HABER VERİLİYOR mu?

⚠ NEDEN: bir uçta beklenmeyen istisna olduğunda hiçbir yere haber gitmiyordu;
yalnız log dosyasına düşüyordu ve o dosyayı kimse okumuyordu. Bir müşteri
sayfası patlasa, müşteri şikayet edene kadar haberimiz olmuyordu.

Sınananlar:
  · istisna → uyarı gönderiliyor
  · AYNI hata spam yapmıyor (döngüye giren bir uç kanalı kullanılamaz kılardı)
  · FARKLI hata ayrı uyarı alıyor (susturma fazla geniş olmamalı)
  · susturulan tekrarlar SAYILIYOR ve mesajda yazıyor
  · uyarı gönderimi patlasa bile istek BOZULMUYOR
  · istemciye yığın izi / iç hata metni SIZMIYOR
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.services import hata_uyari  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


GONDERILEN: list[str] = []


def _sahte_telegram(text: str) -> bool:
    GONDERILEN.append(text)
    return True


def _hata(tur=ValueError, mesaj="patladi"):
    try:
        raise tur(mesaj)
    except Exception as e:  # noqa: BLE001
        return e


import app.services.telegram as _tg  # noqa: E402
_tg_gercek = _tg.send_message
_tg.send_message = _sahte_telegram

try:
    print("\n── ilk hata haber veriliyor ──")
    hata_uyari._SON.clear(); hata_uyari._SAYAC.clear(); GONDERILEN.clear()
    es("uyarı gönderildi", True, hata_uyari.bildir("GET", "/api/deneme", _hata()))
    es("tek mesaj", 1, len(GONDERILEN))
    _m = GONDERILEN[0]
    es("yol mesajda", True, "/api/deneme" in _m)
    es("hata türü mesajda", True, "ValueError" in _m)
    es("yığın izi mesajda", True, "Traceback" in _m or "raise" in _m)

    print("\n── AYNI hata SPAM YAPMIYOR ──")
    # Döngüye giren bir uç dakikada yüzlerce mesaj atardı; kanal kullanılamaz
    # hale gelir ve bildirim fiilen susturulmuş olurdu.
    for _ in range(50):
        hata_uyari.bildir("GET", "/api/deneme", _hata())
    es("50 tekrar YENİ mesaj üretmedi", 1, len(GONDERILEN))
    es("tekrarlar sayılıyor", True, hata_uyari._SAYAC.get(
        hata_uyari._parmak_izi("/api/deneme", _hata())) == 50)

    print("\n── FARKLI hata AYRI uyarı alıyor ──")
    es("başka uç → yeni uyarı", True,
       hata_uyari.bildir("GET", "/api/baska", _hata()))
    es("başka istisna türü → yeni uyarı", True,
       hata_uyari.bildir("GET", "/api/deneme", _hata(KeyError, "yok")))
    es("toplam 3 mesaj", 3, len(GONDERILEN))

    print("\n── bekleme sonrası tekrar haber veriliyor ──")
    _iz = hata_uyari._parmak_izi("/api/deneme", _hata())
    hata_uyari._SON[_iz] = 0          # süre dolmuş say
    es("bekleme dolunca yeni uyarı", True,
       hata_uyari.bildir("GET", "/api/deneme", _hata()))
    es("mesajda tekrar sayısı yazıyor", True,
       "kez" in GONDERILEN[-1])

    print("\n── uyarı PATLASA BİLE çağıran bozulmaz ──")
    def _patlayan(text):
        raise RuntimeError("telegram öldü")
    _tg.send_message = _patlayan
    hata_uyari._SON.clear()
    es("istisna yükseltmiyor", False, hata_uyari.bildir("GET", "/api/x", _hata()))
    _tg.send_message = _sahte_telegram

    print("\n── uçtan uca: patlayan uç 500 veriyor, AYRINTI SIZMIYOR ──")
    _app = FastAPI()
    from app.main import beklenmeyen_hata  # noqa: E402
    _app.add_exception_handler(Exception, beklenmeyen_hata)

    @_app.get("/patlat")
    def _patlat():
        raise RuntimeError("GİZLİ: veritabanı şifresi hatalı")

    _c = TestClient(_app, raise_server_exceptions=False)
    hata_uyari._SON.clear(); GONDERILEN.clear()
    _r = _c.get("/patlat")
    es("500 dönüyor", 500, _r.status_code)
    _govde = _r.text
    es("iç hata metni SIZMIYOR", False, "GİZLİ" in _govde)
    es("yığın izi SIZMIYOR", False, "Traceback" in _govde)
    es("kullanıcıya sade mesaj", True, "Beklenmeyen bir hata" in _govde)
    es("bize haber gitti", True, len(GONDERILEN) == 1 and "/patlat" in GONDERILEN[0])
    es("iç hata metni BİZE geldi", True, "GİZLİ" in GONDERILEN[0])
finally:
    _tg.send_message = _tg_gercek
    hata_uyari._SON.clear(); hata_uyari._SAYAC.clear()

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
