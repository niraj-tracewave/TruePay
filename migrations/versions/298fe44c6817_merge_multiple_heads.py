"""Merge multiple heads

Revision ID: 298fe44c6817
Revises: 35300dda060c, 584a3f500ff6
Create Date: 2025-08-13 13:34:58.082243

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '298fe44c6817'
down_revision: Union[str, Sequence[str], None] = ('35300dda060c', '584a3f500ff6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
