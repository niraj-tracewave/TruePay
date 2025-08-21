"""merge heads b3899ba0765e & d0991fcc6155

Revision ID: 761523786d7a
Revises: b3899ba0765e, d0991fcc6155
Create Date: 2025-08-21 18:55:23.322838

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '761523786d7a'
down_revision: Union[str, Sequence[str], None] = ('b3899ba0765e', 'd0991fcc6155')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
