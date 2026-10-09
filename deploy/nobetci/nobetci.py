#!/usr/bin/env python3
"""Nöbetçi — sunucu sağlık denetimi, otomatik onarım ve Telegram raporu.

Her dakika systemd zamanlayıcısıyla (root) çalışır. YALNIZ standart kütüphane:
backend'in sanal ortamı bozulsa bile nöbetçi çalışmaya devam etmeli.

NEDEN (2026-10): Shopify kapanıp alan adı bu sunucuya bağlanınca site uzun
süre 525 (SSL el sıkışması) verdi ve bunu müşteriler fark etti, biz değil.
Reklam trafiği boşa gitti. Artık:

  Denetim                          Onarım (kendiliğinden)
  ───────────────────────────────  ─────────────────────────────────────────
  backend /api/health (yerel)      2 dk üst üste yanıtsız → servisi yeniden başlat
  vitrin (yerel, Next.js)          2 dk üst üste yanıtsız → servisi yeniden başlat
  nginx çalışıyor mu               durmuşsa: önce `nginx -t`, geçerse yeniden başlat
  PostgreSQL (pg_isready)          yanıtsızsa yeniden başlat
  SSL el sıkışması (her alan adı)  — (yapılandırma hatası: yalnız rapor + sebep)
  Dışarıdan (Cloudflare üzerinden) — (yerel sağlamsa sorun CF/DNS/SSL: rapor)
  disk / bellek / takas / yük      disk %90+: günlük ve önbellek temizliği
  sertifika bitiş tarihi           — (20 günden az kalınca rapor)

  Döngü koruması: aynı servis saatte en fazla 3 kez yeniden başlatılır;
  sonra yalnız rapor verilir ("elle bakılmalı").

Rapor: durum değişince (bozuldu / düzeldi / onarıldı) Telegram'a mesaj,
her sabah 09:00'da son 24 saatin özeti. Durum dosyası:
/var/lib/baskici-nobetci/durum.json — panel ve elle kontrol buradan okur.

Kullanım:
  nobetci.py            bir tur denetim (zamanlayıcı bunu çağırır)
  nobetci.py --durum    son durumu yazdır
  nobetci.py --dene     Telegram'a deneme mesajı gönder
  nobetci.py --ozet     günlük özeti şimdi gönder
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Ayarlar (gerekirse /etc/baskici-nobetci.json ile ezilir) ──
AYAR = {
    "env_dosyasi": "/home/baskici/baskici-saas/backend/.env",
    "durum_dizini": "/var/lib/baskici-nobetci",
    "yerel": [
        # ad, adres, Host başlığı, servis (onarımda yeniden başlatılacak)
        {"ad": "Backend (API)", "url": "http://127.0.0.1:8000/api/health", "host": None,
         "servis": "baskici-backend", "zaman_asimi": 8},
        {"ad": "Vitrin (mağaza)", "url": "http://127.0.0.1:3001/robots.txt",
         "host": "bernzcompany.com", "servis": "baskici-storefront", "zaman_asimi": 10},
    ],
    # Dışarıdan, Cloudflare üzerinden — müşterinin gördüğü
    "dis": [
        {"ad": "bernzcompany.com", "url": "https://bernzcompany.com/robots.txt"},
        {"ad": "www.bernzcompany.com", "url": "https://www.bernzcompany.com/robots.txt"},
        {"ad": "magaza.bernzcompany.com", "url": "https://magaza.bernzcompany.com/robots.txt"},
        {"ad": "Mağaza paneli", "url": "https://magazapanel.bernzcompany.com/api/health"},
        {"ad": "Studio paneli", "url": "https://studio.bernzcompany.com/api/health"},
        {"ad": "Sipariş takip", "url": "https://siparistakip.bernzcompany.com/"},
    ],
    # Yerel SSL el sıkışması (nginx'in her alan adına doğru sertifikayı vermesi)
    "ssl_adlari": ["bernzcompany.com", "www.bernzcompany.com", "magaza.bernzcompany.com",
                   "magazapanel.bernzcompany.com", "studio.bernzcompany.com",
                   "siparistakip.bernzcompany.com"],
    "dis_aralik_dk": 3,          # dış denetim sıklığı
    "kaynak_aralik_dk": 5,       # disk/bellek denetim sıklığı
    "esik_ardisik": 2,           # kaç ardışık hatadan sonra onarım
    "saatte_en_fazla_onarim": 3,
    "disk_uyari": 85, "disk_temizlik": 90,
    "bellek_uyari_mb": 400,       # kullanılabilir bellek bunun altına inerse
    "ozet_saati": 9,              # İstanbul saati
}

TR = timezone(timedelta(hours=3))


def _ayar_yukle() -> None:
    p = Path(os.environ.get("NOBETCI_AYAR", "/etc/baskici-nobetci.json"))
    if p.exists():
        try:
            AYAR.update(json.loads(p.read_text()))
        except Exception as e:  # noqa: BLE001
            print(f"[nobetci] ayar dosyası okunamadı: {e}")


# ─── Telegram ────────────────────────────────────────────────

def _env() -> dict:
    d = {}
    try:
        for satir in Path(AYAR["env_dosyasi"]).read_text().splitlines():
            satir = satir.strip()
            if not satir or satir.startswith("#") or "=" not in satir:
                continue
            k, v = satir.split("=", 1)
            d[k.strip()] = v.strip().strip('"').strip("'")   # sonuncu kazanır (dotenv gibi)
    except Exception:  # noqa: BLE001
        pass
    return d


def telegram(metin: str) -> bool:
    env = _env()
    token, sohbet = env.get("TELEGRAM_BOT_TOKEN"), env.get("TELEGRAM_CHAT_ID")
    if not token or not sohbet:
        print("[nobetci] Telegram ayarı yok — mesaj yalnız günlüğe yazıldı")
        return False
    govde = json.dumps({"chat_id": sohbet, "text": metin, "parse_mode": "HTML",
                        "disable_web_page_preview": True}).encode()
    try:
        r = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=govde,
                                   headers={"Content-Type": "application/json"})
        urllib.request.urlopen(r, timeout=10).read()
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[nobetci] Telegram gönderilemedi: {e}")
        return False


# ─── Denetimler ──────────────────────────────────────────────

def http_dene(url: str, host: str | None = None, zaman_asimi: float = 10) -> dict:
    """{ok, kod, ms, hata} — 2xx/3xx/401/404 'ayakta' sayılır (sunucu yanıt verdi)."""
    bas = time.monotonic()
    basliklar = {"User-Agent": "baskici-nobetci/1"}
    if host:
        basliklar["Host"] = host
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=basliklar), timeout=zaman_asimi)
        kod = r.status
    except urllib.error.HTTPError as e:
        kod = e.code
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "kod": None, "ms": int((time.monotonic() - bas) * 1000),
                "hata": _hata_metni(e)}
    ms = int((time.monotonic() - bas) * 1000)
    ok = kod < 500
    return {"ok": ok, "kod": kod, "ms": ms, "hata": None if ok else _kod_aciklama(kod)}


def _kod_aciklama(kod: int) -> str:
    return {
        500: "uygulama hatası (500)", 502: "nginx arkadaki servise ulaşamıyor (502)",
        503: "servis kullanılamıyor (503)", 504: "servis zaman aşımı (504)",
        520: "Cloudflare: sunucu boş/garip yanıt verdi (520)",
        521: "Cloudflare: sunucu bağlantıyı reddetti — nginx kapalı ya da güvenlik duvarı (521)",
        522: "Cloudflare: sunucuya bağlanırken zaman aşımı (522)",
        523: "Cloudflare: sunucuya ulaşılamıyor (523)",
        524: "Cloudflare: sunucu 100 sn'de yanıt vermedi (524)",
        525: "Cloudflare: SSL el sıkışması başarısız — nginx'te bu alan adı için 443 bloğu/sertifika yok (525)",
        526: "Cloudflare: sunucu sertifikası geçersiz — alan adı sertifikada yok ya da süresi dolmuş (526)",
        530: "Cloudflare: DNS/origin hatası (530)",
    }.get(kod, f"HTTP {kod}")


def _hata_metni(e: Exception) -> str:
    m = str(getattr(e, "reason", e))
    if "timed out" in m or isinstance(e, (socket.timeout, TimeoutError)):
        return "zaman aşımı (yanıt yok)"
    if "Connection refused" in m:
        return "bağlantı reddedildi (servis kapalı)"
    return m[:160]


def ssl_dene(ad: str) -> dict:
    """nginx bu alan adı için 443'te el sıkışıyor ve sertifika adı kapsıyor mu?
    Cloudflare Origin sertifikası herkese açık güvenilir değil — zincir değil,
    yalnız ad ve tarih denetlenir."""
    bag = ssl.create_default_context()
    bag.check_hostname = False
    bag.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection(("127.0.0.1", 443), timeout=5) as s:
            with bag.wrap_socket(s, server_hostname=ad) as t:
                der = t.getpeercert(binary_form=True)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "hata": f"el sıkışması başarısız: {_hata_metni(e)}"}
    bilgi = _sertifika_bilgisi(der)
    if bilgi is None:
        return {"ok": True, "gun": None}
    adlar, bitis = bilgi
    kapsar = any(a == ad or (a.startswith("*.") and ad.endswith(a[1:]) and ad.count(".") == a.count("."))
                 for a in adlar)
    gun = (bitis - datetime.now(timezone.utc)).days if bitis else None
    if not kapsar:
        return {"ok": False, "gun": gun, "hata": f"sertifika bu adı kapsamıyor (kapsadığı: {', '.join(adlar)[:120]})"}
    if gun is not None and gun < 0:
        return {"ok": False, "gun": gun, "hata": "sertifikanın süresi dolmuş"}
    return {"ok": True, "gun": gun}


def _sertifika_bilgisi(der: bytes):
    """DER sertifikadan SAN adları + bitiş — openssl komutuyla (stdlib'de ayrıştırıcı yok)."""
    try:
        p = subprocess.run(["openssl", "x509", "-inform", "DER", "-noout", "-enddate", "-ext", "subjectAltName"],
                           input=der, capture_output=True, timeout=5)
        cikti = p.stdout.decode()
    except Exception:  # noqa: BLE001
        return None
    adlar = [x.strip()[4:] for x in cikti.replace("\n", ",").split(",") if x.strip().startswith("DNS:")]
    bitis = None
    for satir in cikti.splitlines():
        if satir.startswith("notAfter="):
            try:
                bitis = datetime.strptime(satir[9:].strip(), "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
            except ValueError:
                pass
    return adlar, bitis


def komut(*arg: str, zaman_asimi: int = 60) -> tuple[int, str]:
    try:
        p = subprocess.run(list(arg), capture_output=True, text=True, timeout=zaman_asimi)
        return p.returncode, (p.stdout + p.stderr).strip()
    except Exception as e:  # noqa: BLE001
        return 1, str(e)


def servis_aktif(ad: str) -> bool:
    return komut("systemctl", "is-active", "--quiet", ad)[0] == 0


def kaynaklar() -> dict:
    d = shutil.disk_usage("/")
    disk = round(100 * d.used / d.total, 1)
    mem = {}
    try:
        for satir in Path("/proc/meminfo").read_text().splitlines():
            k, v = satir.split(":", 1)
            mem[k] = int(v.split()[0]) // 1024
    except (OSError, ValueError):
        pass
    yuk = os.getloadavg()[0]
    balon = None
    kod, cikti = komut("vmware-toolbox-cmd", "stat", "balloon", zaman_asimi=5)
    if kod == 0:
        try:
            balon = int(cikti.split()[0])
        except (ValueError, IndexError):
            pass
    return {"disk_yuzde": disk, "disk_bos_gb": round(d.free / 1e9, 1),
            "bellek_kullanilabilir_mb": mem.get("MemAvailable"), "bellek_toplam_mb": mem.get("MemTotal"),
            "takas_kullanilan_mb": (mem.get("SwapTotal", 0) - mem.get("SwapFree", 0)),
            "yuk": round(yuk, 2), "cekirdek": os.cpu_count(), "balon_mb": balon}


# ─── Durum ve onarım ────────────────────────────────────────

def _durum_yolu() -> Path:
    p = Path(AYAR["durum_dizini"])
    p.mkdir(parents=True, exist_ok=True)
    return p / "durum.json"


def durum_oku() -> dict:
    try:
        return json.loads(_durum_yolu().read_text())
    except Exception:  # noqa: BLE001
        return {}


def durum_yaz(d: dict) -> None:
    gecici = _durum_yolu().with_suffix(".tmp")
    gecici.write_text(json.dumps(d, ensure_ascii=False, indent=1, default=str))
    gecici.replace(_durum_yolu())


def gecmise_ekle(olay: dict) -> None:
    """Olay günlüğü (JSON satırları) — son ~3000 olay tutulur."""
    p = Path(AYAR["durum_dizini"]) / "olaylar.jsonl"
    with p.open("a") as f:
        f.write(json.dumps(olay, ensure_ascii=False, default=str) + "\n")
    try:
        satirlar = p.read_text().splitlines()
        if len(satirlar) > 3500:
            p.write_text("\n".join(satirlar[-3000:]) + "\n")
    except Exception:  # noqa: BLE001
        pass


def onarim_hakki(d: dict, anahtar: str) -> bool:
    simdi = time.time()
    liste = [t for t in d.setdefault("onarimlar", {}).get(anahtar, []) if simdi - t < 3600]
    d["onarimlar"][anahtar] = liste
    return len(liste) < AYAR["saatte_en_fazla_onarim"]


def onarim_kaydet(d: dict, anahtar: str) -> None:
    d.setdefault("onarimlar", {}).setdefault(anahtar, []).append(time.time())


def zaman() -> str:
    return datetime.now(TR).strftime("%d.%m %H:%M")


def tur() -> None:
    d = durum_oku()
    d.setdefault("kontroller", {})
    d.setdefault("istatistik", {})
    simdi = datetime.now(TR)
    mesajlar: list[str] = []

    def sonuc(anahtar: str, ad: str, ok: bool, ayrinti: dict) -> int:
        """Ardışık hata sayacını güncelle; durum DEĞİŞTİYSE mesaj üret."""
        k = d["kontroller"].setdefault(anahtar, {"ad": ad, "ok": True, "ardisik": 0})
        onceki_ok = k.get("ok", True)
        k.update(ad=ad, son=simdi.isoformat(), **ayrinti)
        ist = d["istatistik"].setdefault(anahtar, {"tur": 0, "hata": 0, "ms_toplam": 0})
        ist["tur"] += 1
        if ayrinti.get("ms") is not None:
            ist["ms_toplam"] += ayrinti["ms"]
        if ok:
            if not onceki_ok and k.get("bildirildi"):
                sure = ""
                if k.get("bozuldu"):
                    dk = int((simdi - datetime.fromisoformat(k["bozuldu"])).total_seconds() // 60)
                    sure = f" ({dk} dk sürdü)"
                mesajlar.append(f"✅ <b>{ad}</b> yeniden çalışıyor{sure}")
                gecmise_ekle({"t": simdi.isoformat(), "olay": "duzeldi", "kontrol": anahtar})
            k.update(ok=True, ardisik=0, bildirildi=False, bozuldu=None, hata=None)
        else:
            ist["hata"] += 1
            k["ardisik"] = k.get("ardisik", 0) + 1
            if onceki_ok:
                k["bozuldu"] = simdi.isoformat()
            k["ok"] = False
        return k["ardisik"]

    # 1) Yerel servisler — onarılabilir
    for y in AYAR["yerel"]:
        r = http_dene(y["url"], y.get("host"), y.get("zaman_asimi", 10))
        anahtar = "yerel:" + y["servis"]
        ardisik = sonuc(anahtar, y["ad"], r["ok"], {"kod": r["kod"], "ms": r["ms"], "hata": r["hata"]})
        if not r["ok"] and ardisik >= AYAR["esik_ardisik"]:
            k = d["kontroller"][anahtar]
            if onarim_hakki(d, y["servis"]):
                onarim_kaydet(d, y["servis"])
                komut("systemctl", "restart", y["servis"], zaman_asimi=90)
                time.sleep(20)
                r2 = http_dene(y["url"], y.get("host"), y.get("zaman_asimi", 10))
                if r2["ok"]:
                    mesajlar.append(f"🔧 <b>{y['ad']}</b> yanıt vermiyordu ({r['hata']}) — "
                                    f"servis yeniden başlatıldı, <b>düzeldi</b> ({r2['ms']} ms)")
                    sonuc(anahtar, y["ad"], True, {"kod": r2["kod"], "ms": r2["ms"], "hata": None})
                else:
                    mesajlar.append(f"🚨 <b>{y['ad']}</b> çalışmıyor ({r['hata']}). Yeniden başlatıldı "
                                    f"ama düzelmedi: {r2['hata']}. Günlük: "
                                    f"<code>journalctl -u {y['servis']} -n 50</code>")
                    k["bildirildi"] = True
                gecmise_ekle({"t": simdi.isoformat(), "olay": "onarim", "kontrol": anahtar,
                              "hata": r["hata"], "sonuc": "duzeldi" if r2["ok"] else "duzelmedi"})
            elif not k.get("bildirildi"):
                mesajlar.append(f"🚨 <b>{y['ad']}</b> çalışmıyor ({r['hata']}). Son 1 saatte "
                                f"{AYAR['saatte_en_fazla_onarim']} kez yeniden başlatıldı — "
                                f"döngüye girmemek için durdum, <b>elle bakılmalı</b>.")
                k["bildirildi"] = True

    # 2) nginx ve PostgreSQL
    for servis, ad, dene in (
        ("nginx", "nginx (web sunucusu)", lambda: servis_aktif("nginx")),
        ("postgresql", "PostgreSQL (veritabanı)", lambda: komut("pg_isready", "-q", zaman_asimi=10)[0] == 0),
    ):
        ok = dene()
        anahtar = "servis:" + servis
        ardisik = sonuc(anahtar, ad, ok, {"hata": None if ok else "çalışmıyor"})
        if not ok and ardisik >= 1:
            k = d["kontroller"][anahtar]
            if servis == "nginx":
                kod, cikti = komut("nginx", "-t")
                if kod != 0:
                    if not k.get("bildirildi"):
                        mesajlar.append(f"🚨 <b>nginx durdu ve yapılandırma HATALI</b> — otomatik "
                                        f"başlatmadım (bozuk ayarla başlamaz):\n<code>{cikti[-400:]}</code>")
                        k["bildirildi"] = True
                    continue
            if onarim_hakki(d, servis):
                onarim_kaydet(d, servis)
                komut("systemctl", "restart", servis, zaman_asimi=90)
                time.sleep(5)
                if dene():
                    mesajlar.append(f"🔧 <b>{ad}</b> durmuştu — yeniden başlatıldı, <b>düzeldi</b>")
                    sonuc(anahtar, ad, True, {"hata": None})
                else:
                    mesajlar.append(f"🚨 <b>{ad}</b> durdu, yeniden başlatma işe yaramadı — elle bakılmalı")
                    k["bildirildi"] = True
                gecmise_ekle({"t": simdi.isoformat(), "olay": "onarim", "kontrol": anahtar})
            elif not k.get("bildirildi"):
                mesajlar.append(f"🚨 <b>{ad}</b> çalışmıyor — saatlik onarım hakkı doldu, elle bakılmalı")
                k["bildirildi"] = True

    # 3) SSL el sıkışması + dış erişim (birkaç dakikada bir)
    son_dis = d.get("son_dis_denetim")
    if not son_dis or (time.time() - son_dis) >= AYAR["dis_aralik_dk"] * 60 - 5:
        d["son_dis_denetim"] = time.time()
        for ad in AYAR["ssl_adlari"]:
            r = ssl_dene(ad)
            anahtar = "ssl:" + ad
            sonuc(anahtar, f"SSL {ad}", r["ok"], {"gun": r.get("gun"), "hata": r.get("hata")})
            k = d["kontroller"][anahtar]
            if not r["ok"] and not k.get("bildirildi"):
                mesajlar.append(f"🔒 <b>{ad}</b> SSL sorunu: {r['hata']}.\nCloudflare bu durumda "
                                f"ziyaretçiye 525/526 gösterir. Çözüm: nginx'te bu ad için "
                                f"<code>listen 443 ssl</code> bloğu + Cloudflare Origin sertifikası.")
                k["bildirildi"] = True
            gun = r.get("gun")
            if r["ok"] and gun is not None and gun < 20 and d.get("sertifika_uyari", {}).get(ad) != simdi.date().isoformat():
                d.setdefault("sertifika_uyari", {})[ad] = simdi.date().isoformat()
                mesajlar.append(f"⏳ <b>{ad}</b> sertifikasının bitmesine {gun} gün kaldı")

        yerel_ok = all(d["kontroller"].get("yerel:" + y["servis"], {}).get("ok", True) for y in AYAR["yerel"])
        for x in AYAR["dis"]:
            r = http_dene(x["url"], zaman_asimi=20)
            if not r["ok"]:      # tek seferlik ağ hıçkırığı alarm sayılmasın: bir kez daha dene
                time.sleep(3)
                r = http_dene(x["url"], zaman_asimi=20)
            anahtar = "dis:" + x["ad"]
            sonuc(anahtar, f"{x['ad']} (dışarıdan)", r["ok"], {"kod": r["kod"], "ms": r["ms"], "hata": r["hata"]})
            k = d["kontroller"][anahtar]
            if not r["ok"] and not k.get("bildirildi"):
                ipucu = ("Sunucudaki servisler ÇALIŞIYOR — sorun Cloudflare/DNS/SSL katmanında."
                         if yerel_ok else "Sunucudaki servis de yanıt vermiyor (yukarıdaki uyarıya bakın).")
                mesajlar.append(f"🌐 <b>{x['ad']}</b> dışarıdan açılmıyor: {r['hata']}\n{ipucu}")
                k["bildirildi"] = True

    # 4) Kaynaklar
    son_k = d.get("son_kaynak_denetim")
    if not son_k or (time.time() - son_k) >= AYAR["kaynak_aralik_dk"] * 60 - 5:
        d["son_kaynak_denetim"] = time.time()
        kay = kaynaklar()
        d["kaynaklar"] = {**kay, "zaman": simdi.isoformat()}
        uyarilar = d.setdefault("kaynak_uyari", {})
        if kay["disk_yuzde"] >= AYAR["disk_temizlik"]:
            komut("journalctl", "--vacuum-size=300M")
            komut("apt-get", "clean")
            komut("find", "/var/cache/nginx", "-type", "f", "-mmin", "+60", "-delete")
            sonra = kaynaklar()["disk_yuzde"]
            mesajlar.append(f"💾 Disk %{kay['disk_yuzde']} doluydu — günlükler ve önbellek temizlendi, "
                            f"şimdi %{sonra}. Kalıcı çözüm için yedek klasörü ve /srv/baskici/storage'a bakın.")
        elif kay["disk_yuzde"] >= AYAR["disk_uyari"] and uyarilar.get("disk") != simdi.date().isoformat():
            uyarilar["disk"] = simdi.date().isoformat()
            mesajlar.append(f"💾 Disk %{kay['disk_yuzde']} dolu ({kay['disk_bos_gb']} GB boş)")
        bmb = kay.get("bellek_kullanilabilir_mb") or 0
        if bmb and bmb < AYAR["bellek_uyari_mb"]:
            if uyarilar.get("bellek_son", 0) < time.time() - 6 * 3600:
                uyarilar["bellek_son"] = time.time()
                balon = f", VMware balonu {kay['balon_mb']} MB" if kay.get("balon_mb") else ""
                mesajlar.append(f"🧠 Kullanılabilir bellek düşük: {bmb} MB (takas {kay['takas_kullanilan_mb']} MB"
                                f"{balon}). Site yavaşlayabilir.")
        if kay["yuk"] > (kay["cekirdek"] or 4) * 2 and uyarilar.get("yuk_son", 0) < time.time() - 3 * 3600:
            uyarilar["yuk_son"] = time.time()
            mesajlar.append(f"🔥 İşlemci yükü yüksek: {kay['yuk']} ({kay['cekirdek']} çekirdek)")

    # 5) Günlük özet
    if simdi.hour == AYAR["ozet_saati"] and d.get("son_ozet") != simdi.date().isoformat():
        d["son_ozet"] = simdi.date().isoformat()
        mesajlar.append(ozet_metni(d))
        d["istatistik"] = {}

    d["son_tur"] = simdi.isoformat()
    durum_yaz(d)
    if mesajlar:
        telegram(f"🛡 <b>Nöbetçi</b> · {zaman()}\n\n" + "\n\n".join(mesajlar))
        for m in mesajlar:
            print("[nobetci]", m.replace("<b>", "").replace("</b>", ""))


def ozet_metni(d: dict) -> str:
    satirlar = ["📋 <b>Günlük sistem özeti</b> (son 24 saat)"]
    for anahtar, ist in sorted(d.get("istatistik", {}).items()):
        if not ist.get("tur"):
            continue
        ad = d["kontroller"].get(anahtar, {}).get("ad", anahtar)
        ayakta = 100 * (ist["tur"] - ist["hata"]) / ist["tur"]
        ort = f", ort. {ist['ms_toplam'] // max(1, ist['tur'])} ms" if ist.get("ms_toplam") else ""
        isaret = "✅" if ayakta >= 99.9 else ("⚠️" if ayakta >= 99 else "🚨")
        if anahtar.startswith(("yerel:", "dis:", "servis:")):
            satirlar.append(f"{isaret} {ad}: %{ayakta:.2f} ayakta{ort}")
    kay = d.get("kaynaklar") or {}
    if kay:
        satirlar.append(f"💾 Disk %{kay.get('disk_yuzde')} · 🧠 boş bellek {kay.get('bellek_kullanilabilir_mb')} MB"
                        f" · takas {kay.get('takas_kullanilan_mb')} MB · yük {kay.get('yuk')}")
    sertifikalar = [(k[4:], v.get("gun")) for k, v in d.get("kontroller", {}).items()
                    if k.startswith("ssl:") and v.get("gun") is not None]
    if sertifikalar:
        en_az = min(sertifikalar, key=lambda x: x[1])
        satirlar.append(f"🔒 En yakın sertifika bitişi: {en_az[0]} — {en_az[1]} gün")
    onarim = sum(len(v) for v in d.get("onarimlar", {}).values())
    if onarim:
        satirlar.append(f"🔧 Son saatte otomatik onarım: {onarim}")
    return "\n".join(satirlar)


def _guvenli_tur() -> None:
    try:
        tur()
    except Exception as e:  # noqa: BLE001 — nöbetçinin kendisi çökerse bunu da bildir
        import traceback
        iz = traceback.format_exc()[-600:]
        print(iz)
        d = durum_oku()
        if d.get("son_cokme_bildirimi", 0) < time.time() - 6 * 3600:
            d["son_cokme_bildirimi"] = time.time()
            durum_yaz(d)
            telegram(f"⚠️ <b>Nöbetçi</b> kendi içinde hata verdi: {e}\n<code>{iz}</code>")


def main() -> None:
    _ayar_yukle()
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "--durum":
        print(json.dumps(durum_oku(), ensure_ascii=False, indent=1))
    elif arg == "--dene":
        ok = telegram(f"🛡 <b>Nöbetçi</b> · {zaman()}\nDeneme mesajı — bildirimler bu sohbete gelecek.")
        print("gönderildi" if ok else "GÖNDERİLEMEDİ (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID .env'de var mı?)")
    elif arg == "--ozet":
        telegram(ozet_metni(durum_oku()))
    else:
        _guvenli_tur()


if __name__ == "__main__":
    main()
