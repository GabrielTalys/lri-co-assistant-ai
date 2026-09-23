"""Add optional comment field to scores

Revision ID: 0007_score_comment
Revises: 0006_invite_token_name
Create Date: 2026-03-08
"""

from alembic import op
import sqlalchemy as sa


revision = '0007_score_comment'
down_revision = '0006_invite_token_name'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('scores') as batch_op:
        batch_op.add_column(sa.Column('comment', sa.Text(), nullable=True))


def downgrade() -> None:
    raise NotImplementedError('Downgrade is not supported for this revision.')

