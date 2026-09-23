"""Limit run phase range to 1..5

Revision ID: 0005_limit_run_phase_to_five
Revises: 0004_cycle_scoped_eval_data
Create Date: 2026-03-08
"""

from alembic import op


revision = '0005_limit_run_phase_to_five'
down_revision = '0004_cycle_scoped_eval_data'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('UPDATE runs SET current_phase = 5 WHERE current_phase > 5')
    op.execute('UPDATE runs SET current_phase = 1 WHERE current_phase < 1')

    with op.batch_alter_table('runs') as batch_op:
        batch_op.drop_constraint('ck_runs_phase_range', type_='check')
        batch_op.create_check_constraint('ck_runs_phase_range', 'current_phase >= 1 AND current_phase <= 5')


def downgrade() -> None:
    raise NotImplementedError('Downgrade is not supported for this revision.')
