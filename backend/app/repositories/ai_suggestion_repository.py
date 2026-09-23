from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AISuggestion, AISuggestionStatus


class AISuggestionRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_run(self, run_id: int, cycle: int) -> list[AISuggestion]:
        return self.db.scalars(
            select(AISuggestion)
            .where(AISuggestion.run_id == run_id, AISuggestion.cycle == cycle)
            .order_by(AISuggestion.id.asc())
        ).all()

    def get(self, run_id: int, question_id: int, cycle: int) -> AISuggestion | None:
        return self.db.scalar(
            select(AISuggestion).where(
                AISuggestion.run_id == run_id,
                AISuggestion.question_id == question_id,
                AISuggestion.cycle == cycle,
            )
        )

    def delete_for_question(self, run_id: int, question_id: int, cycle: int) -> None:
        suggestion = self.get(run_id=run_id, question_id=question_id, cycle=cycle)
        if suggestion is not None:
            self.db.delete(suggestion)
            self.db.flush()

    def upsert(
        self,
        run_id: int,
        question_id: int,
        cycle: int,
        status: AISuggestionStatus,
        context_hash: str,
        output: dict | None = None,
        error_message: str | None = None,
    ) -> AISuggestion:
        suggestion = self.get(run_id=run_id, question_id=question_id, cycle=cycle)
        now = datetime.utcnow()

        if suggestion is None:
            suggestion = AISuggestion(
                run_id=run_id,
                question_id=question_id,
                cycle=cycle,
                status=status,
                context_hash=context_hash,
                output=output,
                error_message=error_message,
                created_at=now,
                updated_at=now,
            )
            self.db.add(suggestion)
        else:
            suggestion.status = status
            suggestion.context_hash = context_hash
            suggestion.output = output
            suggestion.error_message = error_message
            suggestion.updated_at = now

        self.db.flush()
        return suggestion
