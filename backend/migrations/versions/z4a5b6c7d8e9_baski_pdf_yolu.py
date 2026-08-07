"""tasarımın vektörel + CMYK baskı PDF'i

Revision ID: z4a5b6c7d8e9
Revises: y3z4a5b6c7d8
Create Date: 2026-08-06
"""
from alembic import op
import sqlalchemy as sa

revision = "z4a5b6c7d8e9"
down_revision = "y3z4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("customer_designs",
                  sa.Column("print_pdf_path", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("customer_designs", "print_pdf_path")
