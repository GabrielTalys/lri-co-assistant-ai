from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import AISuggestion, CanvasResponse, Decision, Export, Invite, Participant, Run, RunStatus, Score, WorkshopSummary


class RunRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        owner_user_id: int,
        title: str,
        ai_mode_enabled: bool = True,
        problem_synthesis: str | None = None,
    ) -> Run:
        run = Run(
            owner_user_id=owner_user_id,
            title=title,
            ai_mode_enabled=ai_mode_enabled,
            problem_synthesis=problem_synthesis,
            status=RunStatus.ACTIVE,
        )
        self.db.add(run)
        self.db.flush()
        return run

    def get(self, run_id: int) -> Run | None:
        return self.db.get(Run, run_id)

    def list_by_owner(self, owner_user_id: int) -> list[Run]:
        return self.db.scalars(select(Run).where(Run.owner_user_id == owner_user_id).order_by(Run.created_at.desc())).all()

    def set_phase(self, run: Run, phase: int) -> Run:
        run.current_phase = phase
        run.updated_at = datetime.utcnow()
        self.db.flush()
        return run

    def set_status(self, run: Run, status: RunStatus) -> Run:
        run.status = status
        run.updated_at = datetime.utcnow()
        self.db.flush()
        return run

    def set_cycle(self, run: Run, cycle: int) -> Run:
        run.current_cycle = cycle
        run.updated_at = datetime.utcnow()
        self.db.flush()
        return run

    def clear_canvas_responses_for_cycle(self, run_id: int, cycle: int) -> None:
        self.db.execute(
            delete(CanvasResponse).where(
                CanvasResponse.run_id == run_id,
                CanvasResponse.cycle == cycle,
            )
        )
        self.db.flush()

    def update(
        self,
        run: Run,
        *,
        ai_mode_enabled: bool | None = None,
        title: str | None = None,
        problem_synthesis: str | None = None,
    ) -> Run:
        if ai_mode_enabled is not None:
            run.ai_mode_enabled = ai_mode_enabled
        if title is not None:
            run.title = title
        if problem_synthesis is not None:
            run.problem_synthesis = problem_synthesis
        run.updated_at = datetime.utcnow()
        self.db.flush()
        return run

    def delete_cascade(self, run_id: int) -> None:
        # Delete children first because FK constraints do not use ON DELETE CASCADE.
        self.db.execute(delete(AISuggestion).where(AISuggestion.run_id == run_id))
        self.db.execute(delete(CanvasResponse).where(CanvasResponse.run_id == run_id))
        self.db.execute(delete(Score).where(Score.run_id == run_id))
        self.db.execute(delete(Invite).where(Invite.run_id == run_id))
        self.db.execute(delete(Decision).where(Decision.run_id == run_id))
        self.db.execute(delete(WorkshopSummary).where(WorkshopSummary.run_id == run_id))
        self.db.execute(delete(Export).where(Export.run_id == run_id))
        self.db.execute(delete(Participant).where(Participant.run_id == run_id))
        self.db.execute(delete(Run).where(Run.id == run_id))
        self.db.flush()
