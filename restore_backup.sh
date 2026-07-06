#!/usr/bin/env bash
#
# Veritabanı yedeğini geri yükler (baskici-YYYYMMDD-HHMMSS.sql.gz).
#
# DİKKAT: Mevcut TÜM veriyi siler ve yedekteki durumla değiştirir.
# Önce backend'i durdurmanız önerilir:  sudo systemctl stop baskici-backend
#
# Kullanım:
#   bash restore_backup.sh                      # en son yedeği seç (liste gösterir)
#   bash restore_backup.sh <dosya.sql.gz>       # belirli bir yedeği geri yükle
#   bash restore_backup.sh --list               # yalnızca yedekleri listele
#
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$HERE/backend/.env"

# BACKUP_DIR: .env'de STORAGE_ROOT/BACKUP_DIR varsa onu kullan, yoksa varsayılan.
STORAGE_ROOT="$(grep -E '^STORAGE_ROOT=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)"
BACKUP_DIR="$(grep -E '^BACKUP_DIR=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)"
if [ -z "${BACKUP_DIR:-}" ]; then
  if [ -n "${STORAGE_ROOT:-}" ]; then
    BACKUP_DIR="$(cd "$(dirname "$STORAGE_ROOT")" 2>/dev/null && pwd)/backups"
  else
    BACKUP_DIR="$HERE/backend/backups"
  fi
fi

echo "📁 Yedek klasörü: $BACKUP_DIR"
if [ ! -d "$BACKUP_DIR" ]; then
  echo "❌ Yedek klasörü bulunamadı. Henüz hiç yedek alınmamış olabilir." >&2
  exit 1
fi

list_backups() {
  ls -1t "$BACKUP_DIR"/baskici-*.sql.gz 2>/dev/null || true
}

if [ "${1:-}" = "--list" ]; then
  echo "Mevcut yedekler (yeniden eskiye):"
  list_backups | while read -r f; do
    printf "  %s  (%s)\n" "$(basename "$f")" "$(du -h "$f" | cut -f1)"
  done
  exit 0
fi

# Yedek dosyasını belirle
if [ -n "${1:-}" ]; then
  FILE="$1"
  [ -f "$FILE" ] || FILE="$BACKUP_DIR/$1"
else
  FILE="$(list_backups | head -1)"
  echo "ℹ️  Dosya verilmedi — en son yedek seçildi."
fi

if [ -z "${FILE:-}" ] || [ ! -f "$FILE" ]; then
  echo "❌ Yedek dosyası bulunamadı: ${1:-<son yedek yok>}" >&2
  echo "   Listelemek için:  bash restore_backup.sh --list" >&2
  exit 1
fi

# DATABASE_URL (pg_dump/psql için +psycopg eklerini temizle)
DBURL="$(grep -E '^DATABASE_URL=' "$ENV_FILE" | cut -d= -f2- | sed 's/+psycopg2//; s/+psycopg//')"
if [ -z "$DBURL" ]; then
  echo "❌ DATABASE_URL $ENV_FILE içinde bulunamadı." >&2
  exit 1
fi

echo
echo "⚠️  GERİ YÜKLENECEK:  $(basename "$FILE")  ($(du -h "$FILE" | cut -f1))"
echo "⚠️  Bu işlem mevcut veritabanındaki TÜM veriyi SİLER ve yedekle değiştirir."
echo "    (Backend'i durdurmanız önerilir: sudo systemctl stop baskici-backend)"
read -r -p "Devam etmek için büyük harfle EVET yazın: " CONFIRM
if [ "$CONFIRM" != "EVET" ]; then
  echo "İptal edildi."; exit 0
fi

echo "🧹 Şema sıfırlanıyor…"
psql "$DBURL" -v ON_ERROR_STOP=1 -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

echo "⤵️  Yedek geri yükleniyor…"
gunzip -c "$FILE" | psql "$DBURL" -v ON_ERROR_STOP=1 >/dev/null

echo "✅ Geri yükleme tamamlandı: $(basename "$FILE")"
echo "   Backend'i tekrar başlatın:  sudo systemctl start baskici-backend"
