from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Participant(Base):
    __tablename__ = 'participants'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey('runs.id'), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    role: Mapped[str] = mapped_column(String(40), default='collaborator')
    is_ai: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_persona_role: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ai_persona_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            '(user_id IS NOT NULL AND email IS NULL) OR (user_id IS NULL AND email IS NOT NULL)',
            name='ck_participants_identity_xor',
        ),
        UniqueConstraint('run_id', 'user_id', name='uq_participant_run_user'),
        UniqueConstraint('run_id', 'email', name='uq_participant_run_email'),
    )
