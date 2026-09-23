"""Add public token and invitee name to invites

Revision ID: 0006_invite_token_name
Revises: 0005_limit_run_phase_to_five
Create Date: 2026-03-08
"""

from alembic import op
import sqlalchemy as sa


revision = '0006_invite_token_name'
down_revision = '0005_limit_run_phase_to_five'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('invites') as batch_op:
        batch_op.add_column(sa.Column('public_token', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('invitee_name', sa.String(length=255), nullable=True))
        batch_op.create_unique_constraint('uq_invites_public_token', ['public_token'])
        batch_op.create_index('ix_invites_public_token', ['public_token'], unique=False)


def downgrade() -> None:
    raise NotImplementedError('Downgrade is not supported for this revision.')
