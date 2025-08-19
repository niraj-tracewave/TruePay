"""Changed payment status values

Revision ID: 584a3f500ff6
Revises: 7a7efa9baca2
Create Date: 2025-08-13 12:46:53.569683
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '584a3f500ff6'
down_revision: Union[str, Sequence[str], None] = '7a7efa9baca2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

old_options = ('pending', 'completed', 'failed', 'created')
new_options = ('created', 'partially_paid', 'paid', 'expired', 'cancelled')

old_type = sa.Enum(*old_options, name='payment_status')
new_type = sa.Enum(*new_options, name='payment_status_new')

table_name = 'payment_details'  # <-- change this to your actual table
column_name = 'status'

def upgrade() -> None:
    bind = op.get_bind()

    # 1. Create new type
    new_type.create(bind, checkfirst=False)

    # 2. Alter column to use new enum
    op.execute(
        f'ALTER TABLE {table_name} ALTER COLUMN {column_name} '
        f'TYPE payment_status_new USING {column_name}::text::payment_status_new'
    )

    # 3. Drop old type
    op.execute('DROP TYPE payment_status')

    # 4. Rename new type to old name
    op.execute('ALTER TYPE payment_status_new RENAME TO payment_status')


def downgrade() -> None:
    bind = op.get_bind()

    # 1. Recreate old type
    old_type.create(bind, checkfirst=False)

    # 2. Alter column back to old enum
    op.execute(
        f'ALTER TABLE {table_name} ALTER COLUMN {column_name} '
        f'TYPE payment_status USING {column_name}::text::payment_status'
    )

    # 3. Drop new type (now unused)
    op.execute('DROP TYPE payment_status_new')
