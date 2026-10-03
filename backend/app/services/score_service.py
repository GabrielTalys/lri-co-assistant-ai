from collections import defaultdict

from sqlalchemy.orm import Session

from app.domain.metrics import ASSESSMENT_METRICS
from app.repositories import InviteRepository, ParticipantRepository, RunRepository, ScoreRepository
from app.services.guards import get_run, get_run_participant


def _capitalize_name(value: str | None) -> str:
    return ' '.join(part.capitalize() for part in (value or '').split())


def _median(values: list[int]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2


class ScoreService:
    def __init__(self, db: Session):
        self.run_repo = RunRepository(db)
        self.participant_repo = ParticipantRepository(db)
        self.score_repo = ScoreRepository(db)
        self.invite_repo = InviteRepository(db)

    def _participant_rows(self, run_id: int, participant_id: int):
        run = get_run(self.run_repo, run_id)
        get_run_participant(self.participant_repo, run_id, participant_id)
        return self.score_repo.list_by_participant(run_id=run_id, participant_id=participant_id, cycle=run.current_cycle)

    def submit_score(
        self,
        run_id: int,
        participant_id: int,
        metric_key: str,
        value: int,
        comment: str | None = None,
    ):
        run = get_run(self.run_repo, run_id)
        get_run_participant(self.participant_repo, run_id, participant_id)

        if metric_key not in ASSESSMENT_METRICS:
            raise ValueError('Unsupported metric key')

        if value < 1 or value > 7:
            raise ValueError('Score must be between 1 and 7')

        existing = self.score_repo.get_by_metric(
            run_id=run_id,
            participant_id=participant_id,
            metric_key=metric_key,
            cycle=run.current_cycle,
        )
        if existing:
            raise ValueError('Metric already submitted by participant')

        normalized_comment = (comment or '').strip() or None
        return self.score_repo.create(
            run_id=run_id,
            participant_id=participant_id,
            metric_key=metric_key,
            cycle=run.current_cycle,
            value=value,
            comment=normalized_comment,
        )

    def get_aggregates(self, run_id: int) -> dict:
        run = get_run(self.run_repo, run_id)

        ai_participant_ids = {p.id for p in self.participant_repo.list_by_run(run_id) if p.is_ai}

        # The AI specialists' evaluations are shown separately (see get_ai_evaluations)
        # and must never influence the consolidated numbers that drive the human
        # GO/PIVOT/ABORT decision.
        values_by_metric: dict[str, list[int]] = defaultdict(list)
        for score in self.score_repo.list_by_run(run_id, cycle=run.current_cycle):
            if score.participant_id not in ai_participant_ids:
                values_by_metric[score.metric_key].append(score.value)

        out = {}
        for metric in ASSESSMENT_METRICS:
            rows = values_by_metric.get(metric, [])
            out[metric] = {
                'avg': (sum(rows) / len(rows)) if rows else 0.0,
                'median': _median(rows),
                'count': len(rows),
                'distribution': {str(n): rows.count(n) for n in range(1, 8)},
            }
        return out

    def get_completion(self, run_id: int) -> dict[str, int | bool]:
        run = get_run(self.run_repo, run_id)

        participants = self.participant_repo.list_by_run(run_id)
        # AI specialists never block or count toward the human completion gate.
        respondents = [p for p in participants if p.role != 'facilitator' and not p.is_ai]
        respondent_ids = {p.id for p in respondents}

        metrics_by_participant: dict[int, set[str]] = defaultdict(set)
        for score in self.score_repo.list_by_run(run_id, cycle=run.current_cycle):
            if score.participant_id in respondent_ids and score.metric_key in ASSESSMENT_METRICS:
                metrics_by_participant[score.participant_id].add(score.metric_key)

        completed = sum(
            1 for p in respondents if set(ASSESSMENT_METRICS).issubset(metrics_by_participant.get(p.id, set()))
        )
        pending_invites = self.invite_repo.count_pending_by_run(run_id)
        required = len(respondents) + pending_invites
        all_done = completed >= required if required > 0 else True

        return {
            'all_done': all_done,
            'required_respondents': required,
            'completed_respondents': completed,
            'pending_invites': pending_invites,
        }

    def get_participant_scores(self, run_id: int, participant_id: int) -> dict[str, int]:
        return {row.metric_key: row.value for row in self._participant_rows(run_id, participant_id)}

    def get_participant_comments(self, run_id: int, participant_id: int) -> dict[str, str]:
        return {
            row.metric_key: row.comment
            for row in self._participant_rows(run_id, participant_id)
            if (row.comment or '').strip()
        }

    def get_comments_by_participant(self, run_id: int) -> list[dict]:
        run = get_run(self.run_repo, run_id)

        ai_participant_ids = {p.id for p in self.participant_repo.list_by_run(run_id) if p.is_ai}
        invite_name_by_participant: dict[int, str] = {}
        for invite in self.invite_repo.list_by_run(run_id):
            participant_id = invite.accepted_participant_id
            if participant_id is None or participant_id in invite_name_by_participant:
                continue
            assigned_name = (invite.participant_name or invite.invitee_name or '').strip()
            if assigned_name:
                invite_name_by_participant[participant_id] = assigned_name

        grouped: dict[int, dict] = {}
        for row in self.score_repo.list_by_run(run_id, cycle=run.current_cycle):
            # Each AI specialist gets its own dedicated card (get_ai_evaluations),
            # never mixed into the generic human comments grid.
            if row.participant_id in ai_participant_ids:
                continue
            comment = (row.comment or '').strip()
            if not comment:
                continue

            participant_label = (
                _capitalize_name(invite_name_by_participant.get(row.participant_id))
                or f'Participant {row.participant_id}'
            )
            entry = grouped.setdefault(
                row.participant_id,
                {
                    'participant_id': row.participant_id,
                    'participant_label': participant_label,
                    'comments': {},
                },
            )
            entry['comments'][row.metric_key] = comment

        return sorted(grouped.values(), key=lambda item: str(item.get('participant_label', '')).lower())

    def reset_participant_scores(self, run_id: int, participant_id: int) -> int:
        run = get_run(self.run_repo, run_id)
        get_run_participant(self.participant_repo, run_id, participant_id)
        return self.score_repo.delete_by_participant(
            run_id=run_id,
            participant_id=participant_id,
            cycle=run.current_cycle,
        )

    def get_ai_evaluations(self, run_id: int) -> list[dict]:
        run = get_run(self.run_repo, run_id)

        evaluations = []
        for ai_participant in self.participant_repo.list_ai_specialists(run_id):
            rows = self.score_repo.list_by_participant(
                run_id=run_id, participant_id=ai_participant.id, cycle=run.current_cycle
            )
            scores = {row.metric_key: {'value': row.value, 'comment': row.comment} for row in rows}
            evaluations.append(
                {
                    'participant_id': ai_participant.id,
                    'role_title': ai_participant.ai_persona_role,
                    'role_description': ai_participant.ai_persona_description,
                    'scores': scores,
                    'is_complete': set(ASSESSMENT_METRICS).issubset(scores),
                }
            )
        return evaluations
