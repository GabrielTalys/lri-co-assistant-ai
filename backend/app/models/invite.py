from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import InviteStatus


class Invite(Base):
    __tablename__ = 'invites'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey('runs.id'), index=True)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    public_token: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    invitee_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    participant_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(40), default='collaborator')
    status: Mapped[InviteStatus] = mapped_column(
        SAEnum(
            InviteStatus,
            name='invite_status',
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=InviteStatus.PENDING,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    accepted_participant_id: Mapped[int | None] = mapped_column(ForeignKey('participants.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
