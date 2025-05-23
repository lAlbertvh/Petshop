from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column('users', 'id', type_=sa.BigInteger())


def downgrade():
    op.alter_column('users', 'id', type_=sa.Integer())
