"""shortcuts value to text

Revision ID: bd20a2292b3e
Revises: b636d9b4f152
Create Date: 2026-05-18 03:33:18.364913
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bd20a2292b3e'
down_revision: Union[str, None] = 'b636d9b4f152'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
