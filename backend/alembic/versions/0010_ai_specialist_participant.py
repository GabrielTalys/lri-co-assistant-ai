"""add ai specialist participant fields

Revision ID: 0010
Revises: 0009_run_problem_synthesis
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0010"
down_revision = "0009_run_problem_synthesis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "participants",
        sa.Column(
            "display_name",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "participants",
        sa.Column(
            "is_ai",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.add_column(
        "participants",
        sa.Column(
            "ai_specialty",
            sa.String(length=255),
            nullable=True,
        ),
    )

    # Batch operations keep this constraint replacement compatible with both
    # PostgreSQL and SQLite. SQLite recreates the table when ALTER TABLE cannot
    # perform the requested constraint change directly.
    with op.batch_alter_table("participants") as batch_op:
        batch_op.drop_constraint("ck_participants_identity_xor", type_="check")
        batch_op.create_check_constraint(
            "ck_participants_identity_xor",
            """
            (
                is_ai = false
                AND (
                    (user_id IS NOT NULL AND email IS NULL)
                    OR
                    (user_id IS NULL AND email IS NOT NULL)
                )
            )
            OR
            (
                is_ai = true
                AND user_id IS NULL
                AND email IS NULL
            )
            """,
        )


def downgrade() -> None:
    with op.batch_alter_table("participants") as batch_op:
        batch_op.drop_constraint("ck_participants_identity_xor", type_="check")
        batch_op.drop_column("ai_specialty")
        batch_op.drop_column("is_ai")
        batch_op.drop_column("display_name")
        batch_op.create_check_constraint(
            "ck_participants_identity_xor",
            "(user_id IS NOT NULL AND email IS NULL) OR (user_id IS NULL AND email IS NOT NULL)",
        )
