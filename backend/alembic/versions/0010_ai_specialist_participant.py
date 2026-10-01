"""Add AI specialist fields to participants

Revision ID: 0010_ai_specialist_participant
Revises: 0009_run_problem_synthesis
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa


revision = '0010_ai_specialist_participant'
down_revision = '0009_run_problem_synthesis'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('participants') as batch_op:
        batch_op.add_column(
            sa.Column('is_ai', sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column('ai_persona_role', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('ai_persona_description', sa.String(length=500), nullable=True))


def downgrade() -> None:
    raise NotImplementedError('Downgrade is not supported for this revision.')
