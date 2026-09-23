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

    def get_question_by_id(self, question_id: int) -> CanvasQuestion | None:
        return self.db.get(CanvasQuestion, question_id)

    def create_question(self, key: str, title: str, prompt_template: str | None = None) -> CanvasQuestion:
        question = CanvasQuestion(key=key, title=title, prompt_template=prompt_template)
        self.db.add(question)
        self.db.flush()
        return question

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

    def list_unanswered_questions(self, run_id: int, cycle: int) -> list[CanvasQuestion]:
        answered_question_ids = set(
            self.db.scalars(
                select(CanvasResponse.question_id)
                .where(CanvasResponse.run_id == run_id, CanvasResponse.cycle == cycle)
            ).all()
        )
        all_questions = self.list_questions()
        return [q for q in all_questions if q.id not in answered_question_ids]
