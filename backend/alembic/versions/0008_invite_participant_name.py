"""Add participant_name field to invites

Revision ID: 0008_invite_participant_name
Revises: 0007_score_comment
Create Date: 2026-03-08
"""

from alembic import op
import sqlalchemy as sa


revision = '0008_invite_participant_name'
down_revision = '0007_score_comment'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('invites') as batch_op:
        batch_op.add_column(sa.Column('participant_name', sa.String(length=255), nullable=True))

    op.execute("UPDATE invites SET participant_name = invitee_name WHERE participant_name IS NULL")


def downgrade() -> None:
    raise NotImplementedError('Downgrade is not supported for this revision.')

