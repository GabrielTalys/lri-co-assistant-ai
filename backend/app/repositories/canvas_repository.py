from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CanvasQuestion, CanvasResponse


class CanvasRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_questions(self) -> list[CanvasQuestion]:
        return self.db.scalars(select(CanvasQuestion).order_by(CanvasQuestion.id.asc())).all()

    def get_question_by_key(self, key: str) -> CanvasQuestion | None:
        return self.db.scalar(select(CanvasQuestion).where(CanvasQuestion.key == key))

    def list_responses_by_run(self, run_id: int, cycle: int) -> list[CanvasResponse]:
        return self.db.scalars(
            select(CanvasResponse)
            .where(CanvasResponse.run_id == run_id, CanvasResponse.cycle == cycle)
            .order_by(CanvasResponse.id.asc())
        ).all()

    def get_response(self, run_id: int, question_id: int, cycle: int) -> CanvasResponse | None:
        return self.db.scalar(
            select(CanvasResponse).where(
                CanvasResponse.run_id == run_id,
                CanvasResponse.question_id == question_id,
                CanvasResponse.cycle == cycle,
            )
        )

    def upsert_response(
        self,
        run_id: int,
        question_id: int,
        participant_id: int,
        cycle: int,
        content: str,
    ) -> CanvasResponse:
        response = self.get_response(run_id=run_id, question_id=question_id, cycle=cycle)
        if response is None:
            response = CanvasResponse(
                run_id=run_id,
                question_id=question_id,
                participant_id=participant_id,
                cycle=cycle,
                content=content,
                updated_at=datetime.utcnow(),
            )
            self.db.add(response)
        else:
            response.participant_id = participant_id
            response.content = content
            response.updated_at = datetime.utcnow()

        self.db.flush()
        return response
