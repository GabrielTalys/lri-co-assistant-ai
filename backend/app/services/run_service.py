from app.domain.phases import advance_phase
from app.models.enums import RunStatus
from app.repositories import CanvasRepository, InviteRepository, ParticipantRepository, RunRepository


class PhaseAdvanceBlockedError(ValueError):
    pass


class RunService:
    def __init__(
        self,
        run_repo: RunRepository,
        participant_repo: ParticipantRepository,
        invite_repo: InviteRepository,
        canvas_repo: CanvasRepository,
    ):
        self.run_repo = run_repo
        self.participant_repo = participant_repo
        self.invite_repo = invite_repo
        self.canvas_repo = canvas_repo

    def _response_cycle_for_run(self, run) -> int:
        if run.current_phase != 2 or run.current_cycle <= 1:
            return run.current_cycle

        for cycle in range(run.current_cycle - 1, 0, -1):
            if self.canvas_repo.list_responses_by_run(run.id, cycle=cycle):
                return cycle
        return max(1, run.current_cycle - 1)

    def _has_empty_canvas_fields(self, run) -> bool:
        if run.current_phase > 3:
            return False

        questions = self.canvas_repo.list_questions()
        if not questions:
            return False

        cycle = self._response_cycle_for_run(run)
        responses = {
            response.question_id: response
            for response in self.canvas_repo.list_responses_by_run(run.id, cycle=cycle)
        }

        for question in questions:
            response = responses.get(question.id)
            content = (response.content or '').strip() if response else ''
            if not content:
                return True
        return False

    def _copy_canvas_responses_to_current_cycle(self, run) -> None:
        source_cycle = self._response_cycle_for_run(run)
        if source_cycle == run.current_cycle:
            return

        for response in self.canvas_repo.list_responses_by_run(run.id, cycle=source_cycle):
            self.canvas_repo.upsert_response(
                run_id=run.id,
                question_id=response.question_id,
                participant_id=response.participant_id,
                cycle=run.current_cycle,
                content=response.content,
            )

    def create_run(self, owner_user_id: int, title: str, ai_mode_enabled: bool = True):
        run = self.run_repo.create(
            owner_user_id=owner_user_id,
            title=title,
            ai_mode_enabled=ai_mode_enabled,
        )
        if not self.participant_repo.find_by_user(run.id, owner_user_id):
            self.participant_repo.create_with_user(run.id, owner_user_id, role='facilitator')
        return run

    def list_runs(self, owner_user_id: int):
        return self.run_repo.list_by_owner(owner_user_id)

    def get_owned_run(self, run_id: int, owner_user_id: int):
        run = self.run_repo.get(run_id)
        if run is None or run.owner_user_id != owner_user_id:
            raise ValueError('Run not found')
        return run

    def get_run_for_participant(self, run_id: int, participant_id: int):
        run = self.run_repo.get(run_id)
        if run is None:
            raise ValueError('Run not found')
        participant = self.participant_repo.get(participant_id)
        if participant is None or participant.run_id != run_id:
            raise ValueError('Run not found')
        return run

    def advance_phase(self, run_id: int, owner_user_id: int):
        run = self.get_owned_run(run_id, owner_user_id)
        if self._has_empty_canvas_fields(run):
            raise PhaseAdvanceBlockedError('Fill every canvas field before advancing to the next phase.')
        if run.current_phase == 2 and run.current_cycle == 1 and self.invite_repo.count_by_run(run.id) < 1:
            raise PhaseAdvanceBlockedError('Generate at least one invite link in phase 2 before advancing to phase 3.')
        next_phase = advance_phase(run.current_phase)
        if run.current_phase == 2 and next_phase == 3:
            self._copy_canvas_responses_to_current_cycle(run)

        self.run_repo.set_phase(run, next_phase)
        return run

    def update_run(
        self,
        run_id: int,
        owner_user_id: int,
        *,
        ai_mode_enabled: bool | None = None,
        title: str | None = None,
        problem_synthesis: str | None = None,
    ):
        run = self.get_owned_run(run_id, owner_user_id)
        self.run_repo.update(
            run,
            ai_mode_enabled=ai_mode_enabled,
            title=title,
            problem_synthesis=problem_synthesis,
        )
        return run

    def finalize_run(self, run_id: int, owner_user_id: int):
        run = self.get_owned_run(run_id=run_id, owner_user_id=owner_user_id)
        if run.current_phase != 5:
            raise ValueError('Decision can only be recorded in phase 5')
        run.current_phase = max(5, run.current_phase)
        self.run_repo.set_status(run, RunStatus.COMPLETED)
        return run

    def pivot_run(self, run_id: int, owner_user_id: int):
        run = self.get_owned_run(run_id=run_id, owner_user_id=owner_user_id)
        if run.current_phase != 5:
            raise ValueError('Decision can only be recorded in phase 5')

        self.run_repo.update(run, problem_synthesis='')
        self.run_repo.set_phase(run, 2)
        self.run_repo.set_cycle(run, run.current_cycle + 1)
        self.run_repo.set_status(run, RunStatus.ACTIVE)
        return run

    def list_participants(self, run_id: int, owner_user_id: int):
        self.get_owned_run(run_id, owner_user_id)
        return self.participant_repo.list_by_run(run_id)

    def delete_run(self, run_id: int, owner_user_id: int):
        run = self.get_owned_run(run_id, owner_user_id)
        self.run_repo.delete_cascade(run.id)
