# Baskıcı SaaS

Multi-tenant baskı operasyon yönetim sistemi.

## Yapı

- `backend/` — FastAPI + SQLAlchemy + PostgreSQL
- `frontend/` — Vite + React (sonra)
- `docs/` — Mimari ve operasyon notları

## Geliştirme

Backend lokal çalıştırma:

```bash
cd backend
uv venv
source .venv/bin/activate
uv pip install -e .
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

## Multi-tenancy

Her tabloda `tenant_id` foreign key var. Her request middleware'de
`request.state.tenant_id` set edilir (JWT'den). Tüm sorgular bunu
kullanır → tenant izolasyonu garantili.

## Platform adapter

Shopify ve İkas için `app/adapters/` altında ayrı modüller. Pipeline
kodu doğrudan adapter çağırmaz, factory üzerinden geçer.
