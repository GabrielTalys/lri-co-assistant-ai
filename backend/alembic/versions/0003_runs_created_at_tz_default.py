"""runs created_at tz default

Revision ID: 0003_runs_created_at_tz_default
Revises: 0002_architecture_refactor
Create Date: 2026-03-04
"""


revision = '0003_runs_created_at_tz_default'
down_revision = '0002_architecture_refactor'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This migration was previously applied in environments where the file
    # was missing from source control. Keep it as a no-op to restore the
    # revision chain and allow Alembic to run normally.
    pass


def downgrade() -> None:
    pass
