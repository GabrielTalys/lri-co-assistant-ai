from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import RunStatus


class Run(Base):
    __tablename__ = 'runs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    title: Mapped[str] = mapped_column(String(255), default='Untitled Run')
    problem_synthesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_phase: Mapped[int] = mapped_column(Integer, default=1)
    ai_mode_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    current_cycle: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[RunStatus] = mapped_column(
        SAEnum(
            RunStatus,
            name='run_status',
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=RunStatus.ACTIVE,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint('current_phase >= 1 AND current_phase <= 5', name='ck_runs_phase_range'),
        CheckConstraint('current_cycle >= 1', name='ck_runs_cycle_range'),
    )
