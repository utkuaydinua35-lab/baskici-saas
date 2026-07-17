#!/usr/bin/env bash
# Frontend'leri build edip serve dizinlerine kopyalar. baskici kullanıcısıyla
# SUDO'SUZ çalışır — tek şart (root'ta BİR KEZ):
#   mkdir -p /srv/baskici/frontend /srv/baskici/panel
#   chown -R baskici:caddy /srv/baskici/frontend /srv/baskici/panel
# (Caddy'ye yalnız okuma yeter; dosyalar zaten herkes-okur oluşur.)
set -e
REPO="$(cd "$(dirname "$0")" && pwd)"

# Baskıcı paneli
cd "$REPO/frontend"
[ -d node_modules ] || { echo "[deploy_frontend] frontend npm install..."; npm install --no-audit --no-fund; }
echo "[deploy_frontend] baskici frontend build..."
npm run build
echo "[deploy_frontend] kopyala -> /srv/baskici/frontend/dist"
rsync -a --delete "$REPO/frontend/dist/" /srv/baskici/frontend/dist/

# Mağaza paneli (BERNZ Commerce) — Caddy'de panel domain'i yayınlanınca
# buradan servis edilecek; şimdiden güncel tutulur.
if [ -d "$REPO/panel" ]; then
  cd "$REPO/panel"
  [ -d node_modules ] || { echo "[deploy_frontend] panel npm install..."; npm install --no-audit --no-fund; }
  echo "[deploy_frontend] magaza paneli build..."
  npm run build
  echo "[deploy_frontend] kopyala -> /srv/baskici/panel/dist"
  mkdir -p /srv/baskici/panel
  rsync -a --delete "$REPO/panel/dist/" /srv/baskici/panel/dist/
fi

echo "[deploy_frontend] OK"
