from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Participant


class ParticipantRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_with_user(self, run_id: int, user_id: int, role: str) -> Participant:
        participant = Participant(run_id=run_id, user_id=user_id, email=None, role=role)
        self.db.add(participant)
        self.db.flush()
        return participant

    def create_with_email(self, run_id: int, email: str, role: str) -> Participant:
        participant = Participant(run_id=run_id, user_id=None, email=email, role=role)
        self.db.add(participant)
        self.db.flush()
        return participant

    def get(self, participant_id: int) -> Participant | None:
        return self.db.get(Participant, participant_id)

    def list_by_run(self, run_id: int) -> list[Participant]:
        return self.db.scalars(select(Participant).where(Participant.run_id == run_id).order_by(Participant.id.asc())).all()

    def find_by_user(self, run_id: int, user_id: int) -> Participant | None:
        return self.db.scalar(select(Participant).where(Participant.run_id == run_id, Participant.user_id == user_id))

    def find_by_email(self, run_id: int, email: str) -> Participant | None:
        return self.db.scalar(select(Participant).where(Participant.run_id == run_id, Participant.email == email))
