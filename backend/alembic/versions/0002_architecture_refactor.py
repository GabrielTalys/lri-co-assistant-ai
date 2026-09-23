"""architecture refactor

Revision ID: 0002_architecture_refactor
Revises: 0001_initial
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa


revision = '0002_architecture_refactor'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


run_status_enum = sa.Enum('active', 'completed', 'archived', name='run_status')
invite_status_enum = sa.Enum('pending', 'accepted', 'expired', 'revoked', name='invite_status')
ai_suggestion_status_enum = sa.Enum('queued', 'running', 'succeeded', 'failed', 'stale', name='ai_suggestion_status')


def upgrade() -> None:
    # Drop extension tables that depend on projects first.
    op.drop_table('exports')
    op.drop_table('workshop_summaries')
    op.drop_table('decisions')

    # Drop legacy core tables.
    op.drop_table('assessment_scores')
    op.drop_table('assessment_respondents')
    op.drop_table('assessment_sessions')
    op.drop_table('field_suggestions')
    op.drop_table('ai_jobs')
    op.drop_table('phase_entries')
    op.drop_table('participants')
    op.drop_table('invites')
    op.drop_table('project_cycles')
    op.drop_table('projects')

    # Drop legacy enum types left by dropped tables.
    op.execute('DROP TYPE IF EXISTS assessmentcriterion')
    op.execute('DROP TYPE IF EXISTS actortype')
    op.execute('DROP TYPE IF EXISTS decisiontype')
    op.execute('DROP TYPE IF EXISTS jobstatus')
    op.execute('DROP TYPE IF EXISTS jobtype')
    op.execute('DROP TYPE IF EXISTS phase')

    # New core architecture tables.
    op.create_table(
        'runs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('owner_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title', sa.String(255), nullable=False, server_default='Untitled Run'),
        sa.Column('current_phase', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('ai_mode_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('status', run_status_enum, nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('current_phase >= 1 AND current_phase <= 7', name='ck_runs_phase_range'),
    )
    op.create_index('ix_runs_owner_user_id', 'runs', ['owner_user_id'])

    op.create_table(
        'participants',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('run_id', sa.Integer(), sa.ForeignKey('runs.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('role', sa.String(40), nullable=False, server_default='collaborator'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            '(user_id IS NOT NULL AND email IS NULL) OR (user_id IS NULL AND email IS NOT NULL)',
            name='ck_participants_identity_xor',
        ),
        sa.UniqueConstraint('run_id', 'user_id', name='uq_participant_run_user'),
        sa.UniqueConstraint('run_id', 'email', name='uq_participant_run_email'),
    )
    op.create_index('ix_participants_run_id', 'participants', ['run_id'])
    op.create_index('ix_participants_user_id', 'participants', ['user_id'])
    op.create_index('ix_participants_email', 'participants', ['email'])

    op.create_table(
        'invites',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('run_id', sa.Integer(), sa.ForeignKey('runs.id'), nullable=False),
        sa.Column('token_hash', sa.String(255), nullable=False),
        sa.Column('role', sa.String(40), nullable=False, server_default='collaborator'),
        sa.Column('status', invite_status_enum, nullable=False, server_default='pending'),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('accepted_participant_id', sa.Integer(), sa.ForeignKey('participants.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('token_hash', name='uq_invites_token_hash'),
    )
    op.create_index('ix_invites_run_id', 'invites', ['run_id'])
    op.create_index('ix_invites_token_hash', 'invites', ['token_hash'])

    op.create_table(
        'canvas_questions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('key', sa.String(120), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('prompt_template', sa.Text(), nullable=True),
        sa.UniqueConstraint('key', name='uq_canvas_questions_key'),
    )
    op.create_index('ix_canvas_questions_key', 'canvas_questions', ['key'])

    op.create_table(
        'canvas_responses',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('run_id', sa.Integer(), sa.ForeignKey('runs.id'), nullable=False),
        sa.Column('question_id', sa.Integer(), sa.ForeignKey('canvas_questions.id'), nullable=False),
        sa.Column('participant_id', sa.Integer(), sa.ForeignKey('participants.id'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('run_id', 'question_id', name='uq_canvas_response_run_question'),
    )
    op.create_index('ix_canvas_responses_run_id', 'canvas_responses', ['run_id'])
    op.create_index('ix_canvas_responses_question_id', 'canvas_responses', ['question_id'])
    op.create_index('ix_canvas_responses_participant_id', 'canvas_responses', ['participant_id'])

    op.create_table(
        'ai_suggestions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('run_id', sa.Integer(), sa.ForeignKey('runs.id'), nullable=False),
        sa.Column('question_id', sa.Integer(), sa.ForeignKey('canvas_questions.id'), nullable=False),
        sa.Column('status', ai_suggestion_status_enum, nullable=False, server_default='queued'),
        sa.Column('context_hash', sa.String(64), nullable=False),
        sa.Column('output', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('run_id', 'question_id', name='uq_ai_suggestion_run_question'),
    )
    op.create_index('ix_ai_suggestions_run_id', 'ai_suggestions', ['run_id'])
    op.create_index('ix_ai_suggestions_question_id', 'ai_suggestions', ['question_id'])
    op.create_index('ix_ai_suggestions_context_hash', 'ai_suggestions', ['context_hash'])

    op.create_table(
        'scores',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('run_id', sa.Integer(), sa.ForeignKey('runs.id'), nullable=False),
        sa.Column('participant_id', sa.Integer(), sa.ForeignKey('participants.id'), nullable=False),
        sa.Column('metric_key', sa.String(80), nullable=False),
        sa.Column('value', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('run_id', 'participant_id', 'metric_key', name='uq_score_run_participant_metric'),
    )
    op.create_index('ix_scores_run_id', 'scores', ['run_id'])
    op.create_index('ix_scores_metric_key', 'scores', ['metric_key'])

    # Extension tables now reference runs instead of projects.
    op.create_table(
        'decisions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('run_id', sa.Integer(), sa.ForeignKey('runs.id'), nullable=False),
        sa.Column('decision', sa.String(20), nullable=False),
        sa.Column('justification', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_decisions_run_id', 'decisions', ['run_id'])

    op.create_table(
        'workshop_summaries',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('run_id', sa.Integer(), sa.ForeignKey('runs.id'), nullable=False),
        sa.Column('summary_text', sa.Text(), nullable=False),
        sa.Column('highlights_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_workshop_summaries_run_id', 'workshop_summaries', ['run_id'])

    op.create_table(
        'exports',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('run_id', sa.Integer(), sa.ForeignKey('runs.id'), nullable=False),
        sa.Column('file_path', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_exports_run_id', 'exports', ['run_id'])


def downgrade() -> None:
    raise NotImplementedError('Downgrade is not supported for this reset migration.')
