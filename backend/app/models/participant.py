from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Participant(Base):
    __tablename__ = 'participants'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey('runs.id'), index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey('users.id'),
        nullable=True,
        index=True,
    )
    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    # Human participant role or the special AI specialist role.
    role: Mapped[str] = mapped_column(
        String(40),
        default='collaborator',
    )

    # Display name used by the facilitator when identifying participants.
    display_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Identifies whether this participant represents the AI specialist.
    is_ai: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )

    # Specialty configured for the AI specialist.
    ai_specialty: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    __table_args__ = (
        CheckConstraint(
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
            name='ck_participants_identity_xor',
        ),
        UniqueConstraint(
            'run_id',
            'user_id',
            name='uq_participant_run_user',
        ),
        UniqueConstraint(
            'run_id',
            'email',
            name='uq_participant_run_email',
        ),
    )
