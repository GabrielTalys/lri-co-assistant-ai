from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Invite, InviteStatus


class InviteRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        run_id: int,
        token_hash: str,
        public_token: str | None,
        role: str,
        expires_at: datetime,
        invitee_name: str | None = None,
        participant_name: str | None = None,
    ) -> Invite:
        invite = Invite(
            run_id=run_id,
            token_hash=token_hash,
            public_token=public_token,
            invitee_name=invitee_name,
            participant_name=participant_name,
            role=role,
            status=InviteStatus.PENDING,
            expires_at=expires_at,
        )
        self.db.add(invite)
        self.db.flush()
        return invite

    def list_by_run(self, run_id: int) -> list[Invite]:
        return self.db.scalars(select(Invite).where(Invite.run_id == run_id).order_by(Invite.created_at.desc())).all()

    def get_by_token_hash(self, token_hash: str) -> Invite | None:
        return self.db.scalar(select(Invite).where(Invite.token_hash == token_hash))

    def set_status(self, invite: Invite, status: InviteStatus, participant_id: int | None = None) -> Invite:
        invite.status = status
        invite.accepted_participant_id = participant_id
        invite.updated_at = datetime.utcnow()
        self.db.flush()
        return invite

    def count_pending_by_run(self, run_id: int) -> int:
        return int(
            self.db.scalar(
                select(func.count(Invite.id)).where(
                    Invite.run_id == run_id,
                    Invite.status == InviteStatus.PENDING,
                    Invite.accepted_participant_id.is_(None),
                )
            )
            or 0
        )

    def count_by_run(self, run_id: int) -> int:
        return int(self.db.scalar(select(func.count(Invite.id)).where(Invite.run_id == run_id)) or 0)
