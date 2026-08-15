"""add forensic_notes to driver_profiles

Revision ID: a1c2e4f6b8d0
Revises: 43fca35fcc9c
Create Date: 2026-08-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c2e4f6b8d0'
down_revision: Union[str, None] = '43fca35fcc9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('driver_profiles', sa.Column('forensic_notes', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('driver_profiles', 'forensic_notes')
