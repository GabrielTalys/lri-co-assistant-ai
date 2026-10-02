import secrets

from app.models import Participant
from app.repositories import ParticipantRepository, RunRepository, ScoreRepository

MAX_AI_SPECIALISTS = 3
# Mirrors the participants.ai_persona_role / ai_persona_description column sizes.
ROLE_TITLE_MAX_LENGTH = 120
ROLE_DESCRIPTION_MAX_LENGTH = 500


class AISpecialistService:
    """Configures the optional AI expert participants of a run (phase 2 setting).

    Each AI specialist is a normal `Participant` row (is_ai=True) with a synthetic
    email, so it flows through the existing participant/score machinery unchanged.
    A run can have up to MAX_AI_SPECIALISTS of them, each with its own role.
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

    def _get_editable_run(self, run_id: int, owner_user_id: int):
        run = self._get_owned_run(run_id, owner_user_id)
        if not run.ai_mode_enabled:
            raise ValueError('AI mode is disabled for this project')
        if run.current_phase != 2:
            raise ValueError('AI specialists can only be configured in phase 2')
        return run

    def _get_specialist(self, run_id: int, specialist_id: int) -> Participant:
        specialist = self.participant_repo.get_ai_specialist(run_id, specialist_id)
        if specialist is None:
            raise ValueError('AI specialist not found')
        return specialist

    def _normalize(
        self,
        run_id: int,
        role_title: str,
        role_description: str | None,
        *,
        ignore_id: int | None = None,
    ) -> tuple[str, str | None]:
        normalized_role_title = ' '.join((role_title or '').split())
        if not normalized_role_title:
            raise ValueError('Role title is required')
        if len(normalized_role_title) > ROLE_TITLE_MAX_LENGTH:
            raise ValueError(f'Role title must have at most {ROLE_TITLE_MAX_LENGTH} characters')
        normalized_role_description = (role_description or '').strip() or None
        if normalized_role_description and len(normalized_role_description) > ROLE_DESCRIPTION_MAX_LENGTH:
            raise ValueError(
                f'Role context must have at most {ROLE_DESCRIPTION_MAX_LENGTH} characters'
            )

        for other in self.participant_repo.list_ai_specialists(run_id):
            if other.id != ignore_id and (other.ai_persona_role or '').casefold() == normalized_role_title.casefold():
                raise ValueError('This specialist role is already configured for this project')
        return normalized_role_title, normalized_role_description

    def list_specialists(self, run_id: int) -> list[Participant]:
        return self.participant_repo.list_ai_specialists(run_id)

    def create(
        self,
        run_id: int,
        owner_user_id: int,
        role_title: str,
        role_description: str | None = None,
    ) -> Participant:
        self._get_editable_run(run_id, owner_user_id)
        if len(self.participant_repo.list_ai_specialists(run_id)) >= MAX_AI_SPECIALISTS:
            raise ValueError(f'A project can have at most {MAX_AI_SPECIALISTS} AI specialists')

        normalized_role_title, normalized_role_description = self._normalize(
            run_id, role_title, role_description
        )
        # Unique per specialist so several of them fit the (run_id, email) unique constraint.
        email = f'ai-specialist-run-{run_id}-{secrets.token_hex(4)}@lri.local'
        return self.participant_repo.create_ai_specialist(
            run_id, email, normalized_role_title, normalized_role_description
        )

    def update(
        self,
        run_id: int,
        owner_user_id: int,
        specialist_id: int,
        role_title: str,
        role_description: str | None = None,
    ) -> Participant:
        self._get_editable_run(run_id, owner_user_id)
        specialist = self._get_specialist(run_id, specialist_id)
        normalized_role_title, normalized_role_description = self._normalize(
            run_id, role_title, role_description, ignore_id=specialist.id
        )
        return self.participant_repo.update_ai_specialist(
            specialist, normalized_role_title, normalized_role_description
        )

    def remove(self, run_id: int, owner_user_id: int, specialist_id: int) -> None:
        run = self._get_owned_run(run_id, owner_user_id)
        if run.current_phase != 2:
            raise ValueError('AI specialists can only be removed in phase 2')

        specialist = self._get_specialist(run_id, specialist_id)
        if self.score_repo.list_by_participant_all_cycles(run_id, specialist.id):
            raise ValueError('Reset the AI specialist scores before removing it')

        self.participant_repo.delete(specialist)
