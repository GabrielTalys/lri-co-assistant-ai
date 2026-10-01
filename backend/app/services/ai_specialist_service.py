from app.models import Participant
from app.repositories import ParticipantRepository, RunRepository, ScoreRepository


class AISpecialistService:
    """Configures the optional AI expert participant for a run (phase 2 setting).

    The AI specialist is a normal `Participant` row (is_ai=True) with a synthetic
    email, so it flows through the existing participant/score machinery unchanged.
    """

    def __init__(
        self,
        run_repo: RunRepository,
        participant_repo: ParticipantRepository,
        score_repo: ScoreRepository,
    ):
        self.run_repo = run_repo
        self.participant_repo = participant_repo
        self.score_repo = score_repo

    def _get_owned_run(self, run_id: int, owner_user_id: int):
        run = self.run_repo.get(run_id)
        if run is None or run.owner_user_id != owner_user_id:
            raise ValueError('Run not found')
        return run

    def get_config(self, run_id: int) -> Participant | None:
        return self.participant_repo.find_ai_specialist(run_id)

    def upsert(
        self,
        run_id: int,
        owner_user_id: int,
        role_title: str,
        role_description: str | None = None,
    ) -> Participant:
        run = self._get_owned_run(run_id, owner_user_id)
        if not run.ai_mode_enabled:
            raise ValueError('AI mode is disabled for this project')
        if run.current_phase != 2:
            raise ValueError('The AI specialist can only be configured in phase 2')

        normalized_role_title = (role_title or '').strip()
        if not normalized_role_title:
            raise ValueError('Role title is required')
        normalized_role_description = (role_description or '').strip() or None

        existing = self.participant_repo.find_ai_specialist(run_id)
        if existing:
            return self.participant_repo.update_ai_specialist(
                existing, normalized_role_title, normalized_role_description
            )

        email = f'ai-specialist-run-{run_id}@lri.local'
        return self.participant_repo.create_ai_specialist(
            run_id, email, normalized_role_title, normalized_role_description
        )

    def remove(self, run_id: int, owner_user_id: int) -> None:
        run = self._get_owned_run(run_id, owner_user_id)
        if run.current_phase != 2:
            raise ValueError('The AI specialist can only be removed in phase 2')

        existing = self.participant_repo.find_ai_specialist(run_id)
        if existing is None:
            raise ValueError('AI specialist is not configured')
        if self.score_repo.list_by_participant_all_cycles(run_id, existing.id):
            raise ValueError('Reset the AI specialist scores before removing it')

        self.participant_repo.delete(existing)
