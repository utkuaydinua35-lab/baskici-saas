#!/usr/bin/env bash
# Nöbetçiyi kur/güncelle — ROOT olarak çalıştırılır (deploy komutunun içinden).
# Betik root'a ait bir yere KOPYALANIR: root'un baskici kullanıcısının
# yazabildiği bir dosyayı çalıştırması yetki yükseltme kapısı olurdu.
set -euo pipefail
KAYNAK="$(cd "$(dirname "$0")" && pwd)"
install -d -m 755 /usr/local/lib/baskici
install -m 755 -o root -g root "$KAYNAK/nobetci.py" /usr/local/lib/baskici/nobetci.py
install -m 644 -o root -g root "$KAYNAK/baskici-nobetci.service" /etc/systemd/system/baskici-nobetci.service
install -m 644 -o root -g root "$KAYNAK/baskici-nobetci.timer" /etc/systemd/system/baskici-nobetci.timer
install -d -m 750 /var/lib/baskici-nobetci
systemctl daemon-reload
systemctl enable --now baskici-nobetci.timer >/dev/null
echo "NOBETCI KURULDU"
