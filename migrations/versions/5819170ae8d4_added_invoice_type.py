"""added invoice type

Revision ID: 5819170ae8d4
Revises: 70bf62989bbe
Create Date: 2025-08-23 16:50:39.708254

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5819170ae8d4'
down_revision: Union[str, Sequence[str], None] = '70bf62989bbe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Define the ENUM type
invoice_type_enum = sa.Enum(
    "FORECLOSURE",
    "PRE_PAYMENT",
    "EMI",
    name="invoicetype"
)


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Create enum type in Postgres
    invoice_type_enum.create(op.get_bind(), checkfirst=True)

    # 2. Add the column using that enum
    op.add_column(
        "invoices",
        sa.Column("invoice_type", invoice_type_enum, nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    # 1. Drop column first
    op.drop_column("invoices", "invoice_type")

    # 2. Drop enum type
    invoice_type_enum.drop(op.get_bind(), checkfirst=True)
