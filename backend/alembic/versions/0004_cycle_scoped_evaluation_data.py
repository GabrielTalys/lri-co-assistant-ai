"""Add cycle scoping for decisions, scores, canvases, and suggestions"""

from alembic import op
import sqlalchemy as sa


revision = '0004_cycle_scoped_eval_data'
down_revision = '0003_runs_created_at_tz_default'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('runs') as batch_op:
        batch_op.add_column(sa.Column('current_cycle', sa.Integer(), nullable=False, server_default='1'))
        batch_op.create_check_constraint('ck_runs_cycle_range', 'current_cycle >= 1')

    with op.batch_alter_table('canvas_responses') as batch_op:
        batch_op.add_column(sa.Column('cycle', sa.Integer(), nullable=False, server_default='1'))
        batch_op.drop_constraint('uq_canvas_response_run_question', type_='unique')
        batch_op.create_unique_constraint('uq_canvas_response_run_question_cycle', ['run_id', 'question_id', 'cycle'])

    with op.batch_alter_table('scores') as batch_op:
        batch_op.add_column(sa.Column('cycle', sa.Integer(), nullable=False, server_default='1'))
        batch_op.drop_constraint('uq_score_run_participant_metric', type_='unique')
        batch_op.create_unique_constraint('uq_score_run_participant_metric_cycle', ['run_id', 'participant_id', 'metric_key', 'cycle'])

    with op.batch_alter_table('ai_suggestions') as batch_op:
        batch_op.add_column(sa.Column('cycle', sa.Integer(), nullable=False, server_default='1'))
        batch_op.drop_constraint('uq_ai_suggestion_run_question', type_='unique')
        batch_op.create_unique_constraint('uq_ai_suggestion_run_question_cycle', ['run_id', 'question_id', 'cycle'])

    with op.batch_alter_table('decisions') as batch_op:
        batch_op.add_column(sa.Column('cycle', sa.Integer(), nullable=False, server_default='1'))
        batch_op.create_unique_constraint('uq_decision_run_cycle', ['run_id', 'cycle'])


def downgrade() -> None:
    raise NotImplementedError('Downgrade is not supported for this revision.')
