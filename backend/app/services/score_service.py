from collections import defaultdict

from app.domain.metrics import METRICS
from app.repositories import InviteRepository, ParticipantRepository, RunRepository, ScoreRepository


def _capitalize_name(value: str | None) -> str:
    text = (value or '').strip()
    if not text:
        return ''
    return ' '.join(part.capitalize() for part in text.split())


class ScoreService:
    def __init__(
        self,
        run_repo: RunRepository,
        participant_repo: ParticipantRepository,
        score_repo: ScoreRepository,
        invite_repo: InviteRepository,
    ):
        self.run_repo = run_repo
        self.participant_repo = participant_repo
        self.score_repo = score_repo
        self.invite_repo = invite_repo

    def submit_score(
        self,
        run_id: int,
        participant_id: int,
        metric_key: str,
        value: int,
        comment: str | None = None,
    ):
        run = self.run_repo.get(run_id)
        if run is None:
            raise ValueError('Run not found')

        participant = self.participant_repo.get(participant_id)
        if participant is None or participant.run_id != run_id:
            raise ValueError('Participant not found for this run')

        if metric_key not in METRICS:
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
        run = self.run_repo.get(run_id)
        if run is None:
            raise ValueError('Run not found')

        all_scores = self.score_repo.list_by_run(run_id, cycle=run.current_cycle)

        values_by_metric: dict[str, list[int]] = defaultdict(list)
        for score in all_scores:
            values_by_metric[score.metric_key].append(score.value)

        out = {}
        for metric in METRICS:
            rows = values_by_metric.get(metric, [])
            avg = (sum(rows) / len(rows)) if rows else 0.0
            rows_sorted = sorted(rows)
            median = 0.0
            if rows_sorted:
                mid = len(rows_sorted) // 2
                if len(rows_sorted) % 2 == 1:
                    median = float(rows_sorted[mid])
                else:
                    median = (rows_sorted[mid - 1] + rows_sorted[mid]) / 2
            out[metric] = {
                'avg': avg,
                'median': median,
                'count': len(rows),
                'distribution': {str(n): rows.count(n) for n in range(1, 8)},
            }

        return out

    def get_completion(self, run_id: int) -> dict[str, int | bool]:
        run = self.run_repo.get(run_id)
        if run is None:
            raise ValueError('Run not found')

        required_metrics = {'impact', 'feasibility', 'alignment'}
        participants = self.participant_repo.list_by_run(run_id)
        respondents = [p for p in participants if p.role != 'facilitator']
        respondent_ids = {p.id for p in respondents}

        metrics_by_participant: dict[int, set[str]] = defaultdict(set)
        for score in self.score_repo.list_by_run(run_id, cycle=run.current_cycle):
            if score.participant_id not in respondent_ids:
                continue
            if score.metric_key in required_metrics:
                metrics_by_participant[score.participant_id].add(score.metric_key)

        completed = sum(1 for p in respondents if required_metrics.issubset(metrics_by_participant.get(p.id, set())))
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
        run = self.run_repo.get(run_id)
        if run is None:
            raise ValueError('Run not found')
        participant = self.participant_repo.get(participant_id)
        if participant is None or participant.run_id != run_id:
            raise ValueError('Participant not found for this run')
        rows = self.score_repo.list_by_participant(run_id=run_id, participant_id=participant_id, cycle=run.current_cycle)
        return {row.metric_key: row.value for row in rows}

    def get_participant_comments(self, run_id: int, participant_id: int) -> dict[str, str]:
        run = self.run_repo.get(run_id)
        if run is None:
            raise ValueError('Run not found')
        participant = self.participant_repo.get(participant_id)
        if participant is None or participant.run_id != run_id:
            raise ValueError('Participant not found for this run')
        rows = self.score_repo.list_by_participant(run_id=run_id, participant_id=participant_id, cycle=run.current_cycle)
        return {row.metric_key: row.comment for row in rows if (row.comment or '').strip()}

    def get_comments_by_participant(self, run_id: int) -> list[dict]:
        run = self.run_repo.get(run_id)
        if run is None:
            raise ValueError('Run not found')

        participants = {p.id: p for p in self.participant_repo.list_by_run(run_id)}
        invite_name_by_participant: dict[int, str] = {}
        for invite in self.invite_repo.list_by_run(run_id):
            participant_id = invite.accepted_participant_id
            if participant_id is None or participant_id in invite_name_by_participant:
                continue
            assigned_name = (invite.participant_name or invite.invitee_name or '').strip()
            if assigned_name:
                invite_name_by_participant[participant_id] = assigned_name
        rows = self.score_repo.list_by_run(run_id, cycle=run.current_cycle)

        grouped: dict[int, dict] = {}
        for row in rows:
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
        run = self.run_repo.get(run_id)
        if run is None:
            raise ValueError('Run not found')
        participant = self.participant_repo.get(participant_id)
        if participant is None or participant.run_id != run_id:
            raise ValueError('Participant not found for this run')
        return self.score_repo.delete_by_participant(
            run_id=run_id,
            participant_id=participant_id,
            cycle=run.current_cycle,
        )
