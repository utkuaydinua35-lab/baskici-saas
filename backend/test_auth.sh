#!/usr/bin/env bash
# Auth akışını test et — register → login → me
# Önce: uvicorn app.main:app --reload --port 8000 ile sunucu çalışıyor olmalı.

set -e

API="http://localhost:8000"
EMAIL="utku@bernzcompany.com"
PASSWORD="Test1234!"
TENANT_NAME="BERNZ Company"

echo "═══ 1. REGISTER ═══"
REGISTER_RESP=$(curl -s -X POST "$API/api/auth/register" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"$EMAIL\",
    \"password\": \"$PASSWORD\",
    \"full_name\": \"Utku\",
    \"tenant_name\": \"$TENANT_NAME\"
  }")
echo "$REGISTER_RESP" | python3 -m json.tool || echo "$REGISTER_RESP"

TOKEN=$(echo "$REGISTER_RESP" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))")

if [ -z "$TOKEN" ]; then
  echo ""
  echo "⚠ Register başarısız (muhtemelen email zaten kayıtlı). LOGIN deneniyor..."
  echo ""
  echo "═══ 1b. LOGIN ═══"
  LOGIN_RESP=$(curl -s -X POST "$API/api/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\": \"$EMAIL\", \"password\": \"$PASSWORD\"}")
  echo "$LOGIN_RESP" | python3 -m json.tool
  TOKEN=$(echo "$LOGIN_RESP" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))")
fi

if [ -z "$TOKEN" ]; then
  echo "❌ Token alınamadı, çıkılıyor"
  exit 1
fi

echo ""
echo "═══ 2. ME (token ile) ═══"
curl -s "$API/api/auth/me" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo ""
echo "═══ 3. ME (token YOK — 401 beklenir) ═══"
curl -s -w "\nHTTP %{http_code}\n" "$API/api/auth/me"

echo ""
echo "═══ 4. ME (yanlış token — 401 beklenir) ═══"
curl -s -w "\nHTTP %{http_code}\n" "$API/api/auth/me" -H "Authorization: Bearer FAKE_TOKEN"

echo ""
echo "✓ Test tamam"
echo ""
echo "Bu kullanıcıyla devam etmek istersen TOKEN'ı kullan:"
echo "  $TOKEN"
