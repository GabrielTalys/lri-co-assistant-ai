from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AISuggestionStatus


class CanvasQuestion(Base):
    __tablename__ = 'canvas_questions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)


class CanvasResponse(Base):
    __tablename__ = 'canvas_responses'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey('runs.id'))
    question_id: Mapped[int] = mapped_column(ForeignKey('canvas_questions.id'), index=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey('participants.id'), index=True)
    cycle: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content: Mapped[str] = mapped_column(Text, default='')
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('run_id', 'question_id', 'cycle', name='uq_canvas_response_run_question_cycle'),
    )


class AISuggestion(Base):
    __tablename__ = 'ai_suggestions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey('runs.id'), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey('canvas_questions.id'), index=True)
    cycle: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[AISuggestionStatus] = mapped_column(
        SAEnum(
            AISuggestionStatus,
            name='ai_suggestion_status',
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=AISuggestionStatus.QUEUED,
        index=True,
    )
    context_hash: Mapped[str] = mapped_column(String(64), index=True)
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('run_id', 'question_id', 'cycle', name='uq_ai_suggestion_run_question_cycle'),
    )


Index('ix_canvas_responses_run_id', CanvasResponse.run_id)
