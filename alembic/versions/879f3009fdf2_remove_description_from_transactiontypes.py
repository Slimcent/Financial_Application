"""Remove description from TransactionTypes

Revision ID: 879f3009fdf2
Revises: 61e93fcb9b9f
Create Date: 2025-04-01 14:07:10.635865

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '879f3009fdf2'
down_revision: Union[str, None] = '61e93fcb9b9f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('TransactionTypes', 'description')
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('TransactionTypes', sa.Column('description', mysql.VARCHAR(collation='utf8mb4_general_ci', length=255), nullable=True))
    # ### end Alembic commands ###
