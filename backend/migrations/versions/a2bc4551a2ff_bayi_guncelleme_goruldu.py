"""bayi güncelleme notları — kullanıcının en son GÖRDÜĞÜ güncelleme sürümü

Revision ID: a2bc4551a2ff
Revises: b80e50baad93

Bayi paneline yeni bir özellik eklenince bayi bir sonraki girişinde onun
tanıtımını (tutorial) görür. Hangi sürüme kadar gördüğü SUNUCUDA tutulur:
tarayıcıda (localStorage) tutulsaydı telefondan ve bilgisayardan giren bayi
aynı tanıtımı iki kez görür, önbelleği temizleyen her seferinde görürdü.

NULL = hiç görmedi. Güncelleme listesinin kendisi kodda
(frontend/src/lib/bayiGuncellemeler.js) — sürüm numarası oradan gelir.
"""
from alembic import op

revision = "a2bc4551a2ff"
down_revision = "b80e50baad93"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS bayi_guncelleme_goruldu INTEGER")


def downgrade():
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS bayi_guncelleme_goruldu")
