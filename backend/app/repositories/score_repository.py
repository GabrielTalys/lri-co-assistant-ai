from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Score


class ScoreRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_metric(self, run_id: int, participant_id: int, metric_key: str, cycle: int) -> Score | None:
        return self.db.scalar(
            select(Score).where(
                Score.run_id == run_id,
                Score.participant_id == participant_id,
                Score.metric_key == metric_key,
                Score.cycle == cycle,
            )
        )

    def create(
        self,
        run_id: int,
        participant_id: int,
        metric_key: str,
        cycle: int,
        value: int,
        comment: str | None = None,
    ) -> Score:
        score = Score(
            run_id=run_id,
            participant_id=participant_id,
            metric_key=metric_key,
            cycle=cycle,
            value=value,
            comment=comment,
        )
        self.db.add(score)
        self.db.flush()
        return score

    def list_by_participant(self, run_id: int, participant_id: int, cycle: int) -> list[Score]:
        return self.db.scalars(
            select(Score).where(
                Score.run_id == run_id,
                Score.participant_id == participant_id,
                Score.cycle == cycle,
            ).order_by(Score.id.asc())
        ).all()

    def delete_by_participant(self, run_id: int, participant_id: int, cycle: int) -> int:
        result = self.db.execute(
            delete(Score).where(
                Score.run_id == run_id,
                Score.participant_id == participant_id,
                Score.cycle == cycle,
            )
        )
        self.db.flush()
        return result.rowcount or 0

    def list_by_run(self, run_id: int, cycle: int) -> list[Score]:
        return self.db.scalars(
            select(Score)
            .where(Score.run_id == run_id, Score.cycle == cycle)
            .order_by(Score.id.asc())
        ).all()
