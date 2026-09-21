"""kiralama: abonelik planları + ödeme kayıtları

Sistem üçüncü taraflara kiralanacak. Şimdiye kadar tenant.plan serbest
metindi ("trial", "pro"…) ve HİÇBİR ŞEYİ kısıtlamıyordu; active_until yalnız
girişte bakılıyordu, vitrin abonelikten hiç etkilenmiyordu.

Bu migration:
  • plans              — kademeli planlar: sabit aylık ücret + ciro komisyonu
                          + hangi modüllerin açık olduğu
  • abonelik_odemeleri — dönem bazlı ödeme kaydı (havale ya da kart)
  • tenants.plan_id    — kiracının planı (tek doğruluk kaynağı)

MEVCUT KİRACILAR "sahip" planına alınır: tüm modüller açık, ücret yok. Bu
migration deploy edildiğinde var olan hiçbir mağazanın davranışı değişmez.
Kısıtlı planlar yalnız YENİ kiracılara atandığında devreye girer.

Plan fiyatları 0 olarak açılır — gerçek fiyatlar platform panelinden girilir.
Uydurma fiyat yazmak yerine boş bırakmak bilinçli bir tercih.

Revision ID: e1f2a3b4c5d6
Revises: d26b73782211
"""
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e1f2a3b4c5d6"
down_revision = "d26b73782211"
branch_labels = None
depends_on = None

# (kod, ad, sıra, modüller) — modüllerin yetki karşılığı services/abonelik.py'de
PLANLAR = [
    ("sahip",    "Sahip (sınırsız)", 0, ["magaza", "tasarim_studyosu", "uretim", "bayi"]),
    ("basic",    "Basic",            1, ["magaza"]),
    ("standart", "Standart",         2, ["magaza", "tasarim_studyosu"]),
    ("pro",      "Pro",              3, ["magaza", "tasarim_studyosu", "uretim", "bayi"]),
]


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kod", sa.String(30), nullable=False, unique=True),
        sa.Column("ad", sa.String(80), nullable=False),
        sa.Column("aylik_ucret", sa.Numeric(12, 2), nullable=False, server_default="0"),
        # Ciro komisyonu, yüzde olarak (2.50 = %2,5)
        sa.Column("komisyon_orani", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("moduller", postgresql.JSONB(), nullable=False, server_default="[]"),
        # {"urun": 500, "siparis_ay": 2000} — boş = sınırsız
        sa.Column("sinirlar", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("aktif", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sira", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "abonelik_odemeleri",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("plans.id", ondelete="SET NULL"), nullable=True),
        sa.Column("donem_bas", sa.Date(), nullable=False),
        sa.Column("donem_bit", sa.Date(), nullable=False),
        # Tutarlar ödeme ANINDA dondurulur — plan fiyatı sonradan değişse de
        # geçmiş faturalar değişmesin
        sa.Column("sabit_ucret", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("ciro", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("komisyon_orani", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("komisyon", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("toplam", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("yontem", sa.String(20), nullable=False),          # havale | kart
        sa.Column("durum", sa.String(20), nullable=False, server_default="bekliyor"),
        sa.Column("referans", sa.String(200), nullable=True),        # dekont no / iyzico ref
        sa.Column("not_", sa.Text(), nullable=True),
        sa.Column("odendi_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.add_column("tenants", sa.Column(
        "plan_id", postgresql.UUID(as_uuid=True),
        sa.ForeignKey("plans.id", ondelete="SET NULL"), nullable=True))

    # Planları tohumla
    plans = sa.table(
        "plans",
        sa.column("id", postgresql.UUID(as_uuid=True)), sa.column("kod", sa.String),
        sa.column("ad", sa.String), sa.column("sira", sa.Integer),
        sa.column("moduller", postgresql.JSONB),
    )
    sahip_id = None
    for kod, ad, sira, mod in PLANLAR:
        pid = uuid.uuid4()
        if kod == "sahip":
            sahip_id = pid
        op.bulk_insert(plans, [{"id": pid, "kod": kod, "ad": ad, "sira": sira, "moduller": mod}])

    # Var olan her kiracı sınırsız plana — hiçbir mağazanın davranışı değişmesin
    op.execute(sa.text("UPDATE tenants SET plan_id = :p WHERE plan_id IS NULL")
               .bindparams(sa.bindparam("p", sahip_id, type_=postgresql.UUID(as_uuid=True))))


def downgrade() -> None:
    op.drop_column("tenants", "plan_id")
    op.drop_table("abonelik_odemeleri")
    op.drop_table("plans")
