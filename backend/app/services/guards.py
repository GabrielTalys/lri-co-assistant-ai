"""Run and participant lookups shared by the services, with the error each one raises."""

from app.models import Participant, Run
from app.repositories import ParticipantRepository, RunRepository


def get_run(run_repo: RunRepository, run_id: int) -> Run:
    run = run_repo.get(run_id)
    if run is None:
        raise ValueError('Run not found')
    return run


def get_owned_run(run_repo: RunRepository, run_id: int, owner_user_id: int) -> Run:
    run = run_repo.get(run_id)
    if run is None or run.owner_user_id != owner_user_id:
        raise ValueError('Run not found')
    return run


def get_ai_run(
    run_repo: RunRepository,
    run_id: int,
    *,
    phase: int,
    phase_error: str,
    owner_user_id: int | None = None,
) -> Run:
    """A run where AI features may act now: AI mode on and in the given phase."""
    run = get_run(run_repo, run_id) if owner_user_id is None else get_owned_run(run_repo, run_id, owner_user_id)
    if not run.ai_mode_enabled:
        raise ValueError('AI mode is disabled for this project')
    if run.current_phase != phase:
        raise ValueError(phase_error)
    return run


def get_run_participant(participant_repo: ParticipantRepository, run_id: int, participant_id: int) -> Participant:
    participant = participant_repo.get(participant_id)
    if participant is None or participant.run_id != run_id:
        raise ValueError('Participant not found for this run')
    return participant
