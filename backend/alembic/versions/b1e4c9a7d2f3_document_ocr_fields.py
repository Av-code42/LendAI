"""add document file_url and extracted_fields columns

Revision ID: b1e4c9a7d2f3
Revises: 7a0915392f8c
Create Date: 2026-09-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1e4c9a7d2f3'
down_revision: Union[str, None] = '7a0915392f8c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('file_url', sa.String(), nullable=True))
    op.add_column('documents', sa.Column('extracted_fields', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('documents', 'extracted_fields')
    op.drop_column('documents', 'file_url')
