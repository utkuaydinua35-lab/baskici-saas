#!/usr/bin/env bash
# Vitrin (Next.js) build — baskici kullanıcısıyla çalıştırılır.
# Build sonrası root'ta: systemctl restart baskici-storefront
set -e
REPO="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO/storefront"
[ -d node_modules ] || { echo "[deploy_storefront] npm install..."; npm install --no-audit --no-fund; }
echo "[deploy_storefront] build..."
# Ana adres (canonical, site haritası, Meta katalog bağlantıları). NEXT_PUBLIC_*
# DERLEME anında koda gömülür — systemd'deki değer tek başına yetmez.
# 2026-10: Shopify kapandı, mağaza bernzcompany.com'a taşındı (eskiden magaza.).
NEXT_PUBLIC_SITE_URL="${NEXT_PUBLIC_SITE_URL:-https://bernzcompany.com}" npm run build
echo "[deploy_storefront] OK — simdi root'ta: systemctl restart baskici-storefront"
