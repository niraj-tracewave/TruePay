from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '3a8feefa2cb2'
down_revision = '57f455619fa6'
branch_labels = None
depends_on = None

def upgrade():
    # Add temporary BIGINT columns
    op.add_column('subscriptions', sa.Column('start_at_temp', sa.BigInteger(), nullable=True))
    op.add_column('subscriptions', sa.Column('end_at_temp', sa.BigInteger(), nullable=True))
    op.add_column('subscriptions', sa.Column('charge_at_temp', sa.BigInteger(), nullable=True))
    op.add_column('subscriptions', sa.Column('expire_by_temp', sa.BigInteger(), nullable=True))

    # Convert existing TIMESTAMP data to Unix timestamps (BIGINT)
    op.execute("""
        UPDATE subscriptions
        SET start_at_temp = EXTRACT(EPOCH FROM start_at)::BIGINT,
            end_at_temp = EXTRACT(EPOCH FROM end_at)::BIGINT,
            charge_at_temp = EXTRACT(EPOCH FROM charge_at)::BIGINT,
            expire_by_temp = EXTRACT(EPOCH FROM expire_by)::BIGINT
        WHERE start_at IS NOT NULL
           OR end_at IS NOT NULL
           OR charge_at IS NOT NULL
           OR expire_by IS NOT NULL;
    """)

    # Drop the old TIMESTAMP columns
    op.drop_column('subscriptions', 'start_at')
    op.drop_column('subscriptions', 'end_at')
    op.drop_column('subscriptions', 'charge_at')
    op.drop_column('subscriptions', 'expire_by')

    # Rename temporary columns to original names
    op.alter_column('subscriptions', 'start_at_temp', new_column_name='start_at')
    op.alter_column('subscriptions', 'end_at_temp', new_column_name='end_at')
    op.alter_column('subscriptions', 'charge_at_temp', new_column_name='charge_at')
    op.alter_column('subscriptions', 'expire_by_temp', new_column_name='expire_by')

def downgrade():
    # Add temporary TIMESTAMP columns
    op.add_column('subscriptions', sa.Column('start_at_temp', sa.DateTime(), nullable=True))
    op.add_column('subscriptions', sa.Column('end_at_temp', sa.DateTime(), nullable=True))
    op.add_column('subscriptions', sa.Column('charge_at_temp', sa.DateTime(), nullable=True))
    op.add_column('subscriptions', sa.Column('expire_by_temp', sa.DateTime(), nullable=True))

    # Convert BIGINT (Unix timestamps) back to TIMESTAMP
    op.execute("""
        UPDATE subscriptions
        SET start_at_temp = to_timestamp(start_at),
            end_at_temp = to_timestamp(end_at),
            charge_at_temp = to_timestamp(charge_at),
            expire_by_temp = to_timestamp(expire_by)
        WHERE start_at IS NOT NULL
           OR end_at IS NOT NULL
           OR charge_at IS NOT NULL
           OR expire_by IS NOT NULL;
    """)

    # Drop the BIGINT columns
    op.drop_column('subscriptions', 'start_at')
    op.drop_column('subscriptions', 'end_at')
    op.drop_column('subscriptions', 'charge_at')
    op.drop_column('subscriptions', 'expire_by')

    # Rename temporary columns to original names
    op.alter_column('subscriptions', 'start_at_temp', new_column_name='start_at')
    op.alter_column('subscriptions', 'end_at_temp', new_column_name='end_at')
    op.alter_column('subscriptions', 'charge_at_temp', new_column_name='charge_at')
    op.alter_column('subscriptions', 'expire_by_temp', new_column_name='expire_by')