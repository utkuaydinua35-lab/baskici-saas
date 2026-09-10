#!/usr/bin/env bash
# TAM YEDEK GERİ YÜKLEME — veritabanı + dosyalar
#
# ⚠ BU BETİK MEVCUT VERİYİ SİLER. Çalıştırmadan önce ne yaptığını oku.
#
# Kullanım (sunucuda, root olarak):
#     bash GERI-YUKLE.sh /yol/tam-yedek-20260911-030000.tar --onayliyorum
#
# --onayliyorum verilmezse hiçbir şey yapmaz, yalnız ne yapacağını anlatır.
set -euo pipefail

ARSIV="${1:-}"
ONAY="${2:-}"

VT_ADI="${VT_ADI:-baskici}"
STORAGE="${STORAGE:-/srv/baskici/storage}"
UYGULAMA="${UYGULAMA:-/home/baskici/baskici-saas}"
SERVIS="${SERVIS:-baskici-backend}"
KULLANICI="${KULLANICI:-baskici}"

kirmizi() { printf '\033[31m%s\033[0m\n' "$*"; }
yesil()   { printf '\033[32m%s\033[0m\n' "$*"; }

if [[ -z "$ARSIV" || ! -f "$ARSIV" ]]; then
  kirmizi "Arşiv bulunamadı."
  echo "Kullanım: bash GERI-YUKLE.sh /yol/tam-yedek-....tar --onayliyorum"
  exit 1
fi

if [[ $EUID -ne 0 ]]; then
  kirmizi "Bu betik root olarak çalıştırılmalı (sudo bash ...)."
  exit 1
fi

GECICI="$(mktemp -d)"
temizle() { rm -rf "$GECICI"; }
trap temizle EXIT

echo "Arşiv açılıyor (yalnız bilgi dosyaları)…"
tar -xf "$ARSIV" -C "$GECICI" MANIFEST.json 2>/dev/null || true
if [[ -f "$GECICI/MANIFEST.json" ]]; then
  echo "── YEDEK BİLGİSİ ─────────────────────────────"
  cat "$GECICI/MANIFEST.json"
  echo "──────────────────────────────────────────────"
fi

cat <<BILGI

Yapılacaklar:
  1. '$SERVIS' servisi DURDURULACAK
  2. '$VT_ADI' veritabanı SİLİNİP yedekten yeniden kurulacak
  3. '$STORAGE' dizini yedektekiyle DEĞİŞTİRİLECEK
     (mevcut dizin $STORAGE.eski-<zaman> olarak saklanır, silinmez)
  4. Veritabanı göçleri (alembic) çalıştırılacak
  5. Servis yeniden başlatılacak

BILGI

if [[ "$ONAY" != "--onayliyorum" ]]; then
  kirmizi "ONAY YOK — hiçbir şey yapılmadı."
  echo "Gerçekten geri yüklemek için sonuna --onayliyorum ekleyin."
  exit 0
fi

echo "Arşiv açılıyor…"
tar -xf "$ARSIV" -C "$GECICI"

if [[ ! -f "$GECICI/veritabani.sql.gz" ]]; then
  kirmizi "Arşivde veritabani.sql.gz yok — bozuk ya da yanlış arşiv."
  exit 1
fi

echo "1/5 servis durduruluyor…"
systemctl stop "$SERVIS" || true

echo "2/5 veritabanı geri yükleniyor…"
# Açık bağlantılar dropdb'yi engelliyor; önce kes.
sudo -u postgres psql -v ON_ERROR_STOP=1 -c \
  "select pg_terminate_backend(pid) from pg_stat_activity where datname='$VT_ADI' and pid<>pg_backend_pid()" >/dev/null
sudo -u postgres dropdb --if-exists "$VT_ADI"
sudo -u postgres createdb -O "$KULLANICI" "$VT_ADI"
gunzip -c "$GECICI/veritabani.sql.gz" | sudo -u postgres psql -v ON_ERROR_STOP=1 -q "$VT_ADI"
yesil "    veritabanı yüklendi"

echo "3/5 dosyalar geri yükleniyor…"
if [[ -d "$GECICI/storage" ]]; then
  if [[ -d "$STORAGE" ]]; then
    mv "$STORAGE" "$STORAGE.eski-$(date +%Y%m%d-%H%M%S)"
  fi
  mkdir -p "$(dirname "$STORAGE")"
  mv "$GECICI/storage" "$STORAGE"
  chown -R "$KULLANICI":"$KULLANICI" "$STORAGE"
  yesil "    dosyalar yüklendi"
else
  kirmizi "    arşivde storage/ yok — dosyalar ATLANDI"
fi

echo "4/5 göçler (alembic) çalıştırılıyor…"
su - "$KULLANICI" -c "cd $UYGULAMA/backend && .venv/bin/alembic upgrade head" || \
  kirmizi "    göç çalıştırılamadı — elle çalıştırın"

echo "5/5 servis başlatılıyor…"
systemctl start "$SERVIS"
sleep 3
systemctl is-active "$SERVIS" && yesil "servis çalışıyor" || kirmizi "servis başlamadı — journalctl -u $SERVIS"

cat <<SON

$(yesil "GERİ YÜKLEME TAMAM.")

Kontrol listesi:
  · Panele giriş yapıp sipariş listesini aç
  · Bir siparişin tasarım görselini aç (dosyalar geldi mi?)
  · Kalıp PDF'leri arşive DAHİL DEĞİL (yeniden üretilir, 3-4 dk)

Eski dosya dizini $STORAGE.eski-* olarak duruyor; her şey yolundaysa silebilirsiniz.
SON
