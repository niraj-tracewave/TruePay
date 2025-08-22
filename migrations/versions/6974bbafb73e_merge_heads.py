"""merge heads

Revision ID: 6974bbafb73e
Revises: 63d32a063c9a, e59e211d1001
Create Date: 2025-08-20 20:40:07.927037

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6974bbafb73e'
down_revision: Union[str, Sequence[str], None] = ('63d32a063c9a', 'e59e211d1001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
