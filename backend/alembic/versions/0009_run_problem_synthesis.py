"""Add problem_synthesis field to runs

Revision ID: 0009_run_problem_synthesis
Revises: 0008_invite_participant_name
Create Date: 2026-03-23
"""

from alembic import op
import sqlalchemy as sa


revision = '0009_run_problem_synthesis'
down_revision = '0008_invite_participant_name'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('runs') as batch_op:
        batch_op.add_column(sa.Column('problem_synthesis', sa.Text(), nullable=True))


def downgrade() -> None:
    raise NotImplementedError('Downgrade is not supported for this revision.')
