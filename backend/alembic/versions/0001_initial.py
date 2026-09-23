"""initial

Revision ID: 0001_initial
Revises:
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa


revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


phase_enum = sa.Enum('F1', 'F2', 'F3', 'F4', 'F5', name='phase')
job_type_enum = sa.Enum('SUGGEST', 'SUMMARIZE', name='jobtype')
job_status_enum = sa.Enum('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'TIMEOUT', name='jobstatus')
decision_enum = sa.Enum('GO', 'PIVOT', 'ABORT', name='decisiontype')
actor_enum = sa.Enum('RESEARCHER', 'PARTICIPANT', name='actortype')
criterion_enum = sa.Enum('VALUABLE', 'FEASIBLE', 'APPLICABLE', name='assessmentcriterion')


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('owner_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('current_phase', phase_enum, nullable=False),
        sa.Column('current_cycle', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'project_cycles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('cycle_number', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('close_reason', decision_enum, nullable=True),
    )

    op.create_table(
        'invites',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('token_hash', sa.String(255), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'participants',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('invite_id', sa.Integer(), sa.ForeignKey('invites.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('company', sa.String(255), nullable=False),
        sa.Column('consent_accepted_at', sa.DateTime(), nullable=False),
        sa.Column('first_seen_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'phase_entries',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('cycle_number', sa.Integer(), nullable=False),
        sa.Column('phase', phase_enum, nullable=False),
        sa.Column('actor_type', actor_enum, nullable=False),
        sa.Column('actor_id', sa.Integer(), nullable=False),
        sa.Column('field_key', sa.String(120), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('entry_version', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('project_id', 'cycle_number', 'phase', 'actor_type', 'actor_id', 'field_key', name='uq_phase_entry'),
    )

    op.create_table(
        'ai_jobs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('cycle_number', sa.Integer(), nullable=False),
        sa.Column('actor_type', actor_enum, nullable=False),
        sa.Column('actor_id', sa.Integer(), nullable=False),
        sa.Column('job_type', job_type_enum, nullable=False),
        sa.Column('status', job_status_enum, nullable=False),
        sa.Column('input_payload', sa.JSON(), nullable=False),
        sa.Column('output_payload', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('fallback_used', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'field_suggestions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('cycle_number', sa.Integer(), nullable=False),
        sa.Column('phase', phase_enum, nullable=False),
        sa.Column('target_field', sa.String(120), nullable=False),
        sa.Column('source_field', sa.String(120), nullable=False),
        sa.Column('suggested_text', sa.Text(), nullable=False),
        sa.Column('confidence', sa.Integer(), nullable=True),
        sa.Column('rationale', sa.Text(), nullable=True),
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('ai_jobs.id'), nullable=False),
        sa.Column('applied_by_user', sa.Boolean(), nullable=True),
        sa.Column('applied_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'assessment_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('cycle_number', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('frozen_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'assessment_respondents',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('assessment_sessions.id'), nullable=False),
        sa.Column('actor_type', actor_enum, nullable=False),
        sa.Column('actor_id', sa.Integer(), nullable=False),
    )

    op.create_table(
        'assessment_scores',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('assessment_sessions.id'), nullable=False),
        sa.Column('actor_type', actor_enum, nullable=False),
        sa.Column('actor_id', sa.Integer(), nullable=False),
        sa.Column('criterion', criterion_enum, nullable=False),
        sa.Column('score', sa.Integer(), nullable=False),
        sa.Column('justification', sa.Text(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('session_id', 'actor_type', 'actor_id', 'criterion', name='uq_assessment_one'),
    )

    op.create_table(
        'decisions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('cycle_number', sa.Integer(), nullable=False),
        sa.Column('decision', decision_enum, nullable=False),
        sa.Column('justification', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'workshop_summaries',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('cycle_number', sa.Integer(), nullable=False),
        sa.Column('summary_text', sa.Text(), nullable=False),
        sa.Column('highlights_json', sa.JSON(), nullable=True),
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('ai_jobs.id'), nullable=True),
    )

    op.create_table(
        'exports',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('cycle_number', sa.Integer(), nullable=False),
        sa.Column('file_path', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('exports')
    op.drop_table('workshop_summaries')
    op.drop_table('decisions')
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
    op.drop_table('users')
