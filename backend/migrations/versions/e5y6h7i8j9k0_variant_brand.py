"""vitrin varyantlarina marka kolonu (marka -> model hiyerarsisi)

Revision ID: e5y6h7i8j9k0
Revises: d4x5g6h7i8j9
Create Date: 2026-07-04

"""
from alembic import op
import sqlalchemy as sa

revision = "e5y6h7i8j9k0"
down_revision = "d4x5g6h7i8j9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("catalog_variants", sa.Column("brand", sa.String(40), nullable=True))
    # Backfill: phone_models.spec_key eşleşmesinden marka (tenant overlay öncelikli
    # olsun diye önce global, sonra tenant'a özel kayıtlar — sonuncusu kazanır)
    op.execute("""
        UPDATE catalog_variants cv SET brand = pm.brand
        FROM phone_models pm
        WHERE pm.spec_key = cv.model_key AND pm.tenant_id IS NULL AND pm.brand IS NOT NULL
    """)
    op.execute("""
        UPDATE catalog_variants cv SET brand = pm.brand
        FROM phone_models pm
        WHERE pm.spec_key = cv.model_key AND pm.tenant_id = cv.tenant_id AND pm.brand IS NOT NULL
    """)


def downgrade() -> None:
    op.drop_column("catalog_variants", "brand")
