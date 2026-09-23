from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Score(Base):
    __tablename__ = 'scores'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey('runs.id'), index=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey('participants.id'), index=True)
    metric_key: Mapped[str] = mapped_column(String(80), index=True)
    cycle: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    value: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('run_id', 'participant_id', 'metric_key', 'cycle', name='uq_score_run_participant_metric_cycle'),
    )
