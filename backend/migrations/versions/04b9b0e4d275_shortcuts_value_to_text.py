"""shortcuts value to text

Revision ID: 04b9b0e4d275
Revises: bd20a2292b3e
Create Date: 2026-05-18 03:33:59.973587
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '04b9b0e4d275'
down_revision: Union[str, None] = 'bd20a2292b3e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('shortcuts', 'value',
                    existing_type=sa.String(length=50),
                    type_=sa.Text(),
                    existing_nullable=False)


def downgrade() -> None:
    op.alter_column('shortcuts', 'value',
                    existing_type=sa.Text(),
                    type_=sa.String(length=50),
                    existing_nullable=False)
