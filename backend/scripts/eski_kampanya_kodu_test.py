"""Eski ham kampanya kodu vitrine gitmez — services/eski_kampanya_kodu.

Sahadaki sorun: "Gitmeden önce" pop-up'ı ham koddu ve kapatılınca imleç her
yukarı çıktığında yeniden açılıyordu; çark retina'da pikselliydi. Tema
yanıtında eski bloklar çıkarılır, ayarları yeni araçlara taşınır.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.eski_kampanya_kodu import ayikla  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen: {beklenen!r}\n      gercek  : {gercek!r}")


CARK = """<!-- İndirim çarkı — kodları kendi kuponlarınızla değiştirin -->
<div id="bz-wheel-wrap" style="display:none"><div id="bz-wheel-box"><h3>Şansını dene! 🎁</h3>
<p>Çarkı çevir, indirim kodunu kap.</p><button id="bz-wheel-go">ÇEVİR</button></div></div>
<script>(function(){ var GECIKME_SN = 8, TEKRAR_GUN = 7; var D=[
  { yazi: '%10 İNDİRİM', kod: 'CARK10' }, { yazi: 'Tekrar dene', kod: null },
  { yazi: '%15 İNDİRİM', kod: 'CARK15' }]; })();</script>"""
CIKIS = """<!-- Çıkış niyeti pop-up'ı — kodu kendi kuponunuzla değiştirin -->
<div id="bz-exit" style="display:none"><div id="bz-exit-box"><h3>Gitmeden önce… 🎁</h3>
<p>Bu siparişe özel <b>%10 indirim</b> hazırladık.</p><code id="bz-exit-code">HEMENAL10</code>
<button id="bz-exit-cta">Kodu Kullan</button><button id="bz-exit-no">Hayır, teşekkürler</button></div></div>
<style>#bz-exit-bg{position:fixed}</style>
<script>(function(){ var KEY='bz_exit_seen', GUN=3;
  if (matchMedia('(max-width:768px)').matches) setTimeout(ac, 45000); })();</script>"""

print("\n── Ayıklama ──")
kod, cark, cikis = ayikla({"head_html": "<meta x>", "css": "", "body_html": f"<p>önce</p>\n{CARK}\n{CIKIS}\n<p>sonra</p>"})
es("eski bloklar çıkar, kalan kod korunur", "<p>önce</p>\n\n<p>sonra</p>", kod["body_html"])
es("başka alan dokunulmaz", "<meta x>", kod["head_html"])
es("çıkış ayarları", {"enabled": True, "baslik": "Gitmeden önce… 🎁", "metin": "Bu siparişe özel %10 indirim hazırladık.",
                      "kupon": "HEMENAL10", "buton": "Kodu Kullan", "vazgec": "Hayır, teşekkürler",
                      "tekrar_gun": 3, "mobil_gecikme_sn": 45}, cikis)
es("çark dilimleri", [{"yazi": "%10 İNDİRİM", "kod": "CARK10"}, {"yazi": "Tekrar dene", "kod": ""},
                      {"yazi": "%15 İNDİRİM", "kod": "CARK15"}], cark["dilimler"])
es("çark süreleri", (8, 7), (cark["gecikme_sn"], cark["tekrar_gun"]))

print("\n── Kenar durumlar ──")
kod, _, cikis = ayikla({"body_html": CIKIS + "\n" + CIKIS})
es("iki kez yapıştırılan blok: ikisi de çıkar, özel kod boşalır", None, kod)
es("ayar ilk bloktan", "HEMENAL10", cikis["kupon"])
kod, cark, cikis = ayikla({"body_html": "<script>console.log(1)</script>", "css": "a{}"})
es("eski kod yoksa aynen", ({"body_html": "<script>console.log(1)</script>", "css": "a{}"}, None, None), (kod, cark, cikis))
es("özel kod yok", (None, None, None), ayikla(None))

print(f"\nGECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
