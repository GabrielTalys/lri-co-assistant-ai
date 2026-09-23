from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from itertools import count
from pathlib import Path
import re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.domain.metrics import LEGACY_CRITERION_TO_METRIC, METRIC_TO_LEGACY_CRITERION
from app.domain.phases import LEGACY_PHASE_ENUM, LEGACY_PHASE_TO_NUMBER
from app.models import Decision, Export, Participant, Run, User, WorkshopSummary
from app.repositories import AISuggestionRepository, CanvasRepository, InviteRepository, ParticipantRepository, RunRepository, ScoreRepository
from app.schemas.common import (
    AIJobStatusOut,
    AssessmentScoreRequest,
    AssessmentStartRequest,
    DecisionRequest,
    ExportOut,
    InviteOut,
    JoinInviteRequest,
    JoinInviteResponse,
    PhaseEntryPatch,
    PhaseEntryPatchResponse,
    ProjectCreate,
    ProjectOut,
    SummaryGenerateResponse,
)
from app.services.canvas_service import CanvasService
from app.services.invite_service import InviteService
from app.services.pdf_service import build_pdf
from app.services.run_service import PhaseAdvanceBlockedError, RunService
from app.services.score_service import ScoreService

router = APIRouter(tags=['legacy-projects'])

LEGACY_JOB_SEQ = count(1)
LEGACY_JOBS: dict[int, dict] = {}

PHASE1_LEGACY_MAP = {
    'Describe the pain point': 'problem',
    'Characterize the environment': 'stakeholders',
    'Consequences/Benefits': 'research_questions',
    'Identify People Involved': 'hypotheses',
    'What scientific evidence?': 'method',
    'Define the objectives': 'evaluation',
    'What research questions?': 'risks',
}
PHASE2_LEGACY_MAP = {
    'alignment_notes': 'stakeholders',
    'suggested_edits': 'hypotheses',
    'conflicts_consensus': 'risks',
}
PHASE3_LEGACY_MAP = {
    'final_problem_statement': 'method',
    'consolidation_notes': 'evaluation',
}
PHASE5_LEGACY_MAP = {
    'observations': 'risks',
}


def _legacy_phase_from_number(phase: int) -> str:
    return LEGACY_PHASE_ENUM.get(phase, 'F5')


def _legacy_project_out(run: Run) -> ProjectOut:
    phase_number = max(1, min(5, run.current_phase))
    return ProjectOut(
        id=run.id,
        title=run.title,
        current_phase=_legacy_phase_from_number(phase_number),
        current_cycle=run.current_cycle,
    )


def _parse_legacy_phase(phase: str) -> int:
    return LEGACY_PHASE_TO_NUMBER.get(phase, 1)


def _legacy_field_to_canvas_key(field_key: str, phase: str) -> str:
    phase_number = _parse_legacy_phase(phase)
    if phase_number == 1:
        return PHASE1_LEGACY_MAP.get(field_key, 'problem')
    if phase_number == 2:
        return PHASE2_LEGACY_MAP.get(field_key, 'stakeholders')
    if phase_number == 3:
        return PHASE3_LEGACY_MAP.get(field_key, 'method')
    if phase_number == 5:
        return PHASE5_LEGACY_MAP.get(field_key, 'risks')

    slug = re.sub(r'[^a-z0-9]+', '_', field_key.lower()).strip('_')
    return slug or 'problem'


def _new_job(job_type: str, status: str = 'completed') -> int:
    jid = next(LEGACY_JOB_SEQ)
    LEGACY_JOBS[jid] = {'id': jid, 'job_type': job_type, 'status': status, 'fallback_used': True, 'error_message': None}
    return jid


def _run_service(db: Session) -> RunService:
    return RunService(
        run_repo=RunRepository(db),
        participant_repo=ParticipantRepository(db),
        invite_repo=InviteRepository(db),
        canvas_repo=CanvasRepository(db),
    )


def _invite_service(db: Session) -> InviteService:
    return InviteService(
        run_repo=RunRepository(db),
        invite_repo=InviteRepository(db),
        participant_repo=ParticipantRepository(db),
    )


def _canvas_service(db: Session) -> CanvasService:
    return CanvasService(
        run_repo=RunRepository(db),
        participant_repo=ParticipantRepository(db),
        canvas_repo=CanvasRepository(db),
        ai_repo=AISuggestionRepository(db),
    )


def _score_service(db: Session) -> ScoreService:
    return ScoreService(
        run_repo=RunRepository(db),
        participant_repo=ParticipantRepository(db),
        score_repo=ScoreRepository(db),
        invite_repo=InviteRepository(db),
    )


def _ensure_owner(run_id: int, current_user: User, db: Session) -> Run:
    run = RunRepository(db).get(run_id)
    if run is None or run.owner_user_id != current_user.id:
        raise HTTPException(status_code=404, detail='Project not found')
    return run


def _ensure_facilitator_participant(db: Session, run_id: int, user_id: int) -> Participant:
    repo = ParticipantRepository(db)
    participant = repo.find_by_user(run_id, user_id)
    if participant is None:
        participant = repo.create_with_user(run_id, user_id, role='facilitator')
    return participant


@router.post('/projects', response_model=ProjectOut)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    run = _run_service(db).create_run(owner_user_id=current_user.id, title=payload.title, ai_mode_enabled=True)
    db.commit()
    db.refresh(run)
    return _legacy_project_out(run)


@router.get('/projects', response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    runs = _run_service(db).list_runs(current_user.id)
    return [_legacy_project_out(run) for run in runs]


@router.get('/projects/{project_id}', response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    run = _ensure_owner(project_id, current_user, db)
    return _legacy_project_out(run)


@router.post('/projects/{project_id}/advance-phase', response_model=ProjectOut)
def advance_phase(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        run = _run_service(db).advance_phase(project_id, current_user.id)
    except PhaseAdvanceBlockedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    db.refresh(run)
    return _legacy_project_out(run)


@router.post('/projects/{project_id}/invites', response_model=InviteOut)
def create_invite(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    run = _ensure_owner(project_id, current_user, db)
    if run.current_phase <= 1:
        raise HTTPException(status_code=400, detail='Invites allowed from phase F2')

    raw_token, invite = _invite_service(db).create_invite(run_id=project_id, owner_user_id=current_user.id, role='collaborator')
    db.commit()
    invite_url = f'{settings.frontend_public_url.rstrip("/")}/invite/{raw_token}'
    return InviteOut(invite_url=invite_url, expires_at=invite.expires_at)


@router.get('/invite/{token}')
def inspect_invite(token: str, db: Session = Depends(get_db)):
    try:
        invite = _invite_service(db).inspect_invite(token)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {'project_id': invite.run_id, 'expires_at': invite.expires_at}


@router.post('/invite/{token}/join', response_model=JoinInviteResponse)
def join_invite(token: str, payload: JoinInviteRequest, db: Session = Depends(get_db)):
    if not payload.consent:
        raise HTTPException(status_code=400, detail='Consent is required')

    email = f"{re.sub(r'[^a-z0-9]+', '', payload.name.lower()) or 'guest'}-{token[:6]}@invite.local"
    try:
        invite, participant = _invite_service(db).accept_invite(token, email=email)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    db.commit()
    return JoinInviteResponse(participant_id=participant.id, project_id=invite.run_id)


@router.patch('/projects/{project_id}/phases/{phase}/entries', response_model=PhaseEntryPatchResponse)
def patch_phase_entry(
    project_id: int,
    phase: str,
    payload: PhaseEntryPatch,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    run = RunRepository(db).get(project_id)
    if run is None:
        raise HTTPException(status_code=404, detail='Project not found')

    request_phase = _parse_legacy_phase(phase)
    if request_phase > run.current_phase:
        raise HTTPException(status_code=400, detail='Phase not unlocked')

    if payload.actor_type == 'participant':
        participant = ParticipantRepository(db).get(payload.actor_id)
        if participant is None or participant.run_id != project_id:
            raise HTTPException(status_code=403, detail='Invalid participant')
    else:
        participant = _ensure_facilitator_participant(db, project_id, payload.actor_id)

    question_key = _legacy_field_to_canvas_key(payload.field_key, phase)

    try:
        _canvas_service(db).submit_response(
            run_id=project_id,
            question_key=question_key,
            participant_id=participant.id,
            content=payload.content,
            background_tasks=background_tasks,
            allow_dynamic_questions=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.commit()
    ai_job_id = _new_job('suggest', status='completed') if request_phase <= 3 else None
    return PhaseEntryPatchResponse(entry_version=1, ai_job_id=ai_job_id)


@router.get('/ai/jobs/{job_id}', response_model=AIJobStatusOut)
def get_ai_job(job_id: int):
    job = LEGACY_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail='Job not found')
    return AIJobStatusOut(**job)


@router.get('/projects/{project_id}/phases/{phase}/suggestions')
def get_field_suggestions(
    project_id: int,
    phase: str,
    field: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_owner(project_id, current_user, db)
    run = RunRepository(db).get(project_id)
    if run is None:
        raise HTTPException(status_code=404, detail='Project not found')

    question_key = _legacy_field_to_canvas_key(field, phase)
    question = CanvasRepository(db).get_question_by_key(question_key)
    if question is None:
        return {'suggestions': []}

    suggestion = AISuggestionRepository(db).get(
        run_id=project_id,
        question_id=question.id,
        cycle=run.current_cycle,
    )
    if suggestion is None or not suggestion.output:
        return {'suggestions': []}

    return {
        'suggestions': [
            {
                'target_field': field,
                'source_field': field,
                'suggested_text': suggestion.output.get('text', ''),
                'confidence': 6,
                'rationale': 'Generated from current run context.',
            }
        ]
    }


@router.post('/projects/{project_id}/assessment/start')
def start_assessment(
    project_id: int,
    payload: AssessmentStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_owner(project_id, current_user, db)
    return {'session_id': project_id, 'participants': payload.participants}


@router.post('/projects/{project_id}/assessment/score')
def submit_score(project_id: int, payload: AssessmentScoreRequest, db: Session = Depends(get_db)):
    participant_repo = ParticipantRepository(db)
    if payload.actor_type == 'participant':
        participant = participant_repo.get(payload.actor_id)
    else:
        participant = _ensure_facilitator_participant(db, project_id, payload.actor_id)

    if participant is None or participant.run_id != project_id:
        raise HTTPException(status_code=403, detail='Invalid participant')

    metric = LEGACY_CRITERION_TO_METRIC.get(payload.criterion)
    if metric is None:
        raise HTTPException(status_code=400, detail='Unsupported criterion')

    try:
        _score_service(db).submit_score(project_id, participant.id, metric, payload.score)
    except ValueError as exc:
        msg = str(exc)
        if 'already submitted' in msg:
            raise HTTPException(status_code=409, detail='Criterion already submitted for actor') from exc
        raise HTTPException(status_code=400, detail=msg) from exc

    db.commit()
    return {'ok': True}


@router.get('/projects/{project_id}/assessment/consolidated')
def consolidated_assessment(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    run = _ensure_owner(project_id, current_user, db)

    criteria = _score_service(db).get_aggregates(project_id)
    participants = ParticipantRepository(db).list_by_run(project_id)

    per_participant_counts: dict[int, int] = defaultdict(int)
    for score in ScoreRepository(db).list_by_run(project_id, cycle=run.current_cycle):
        if score.metric_key in {'impact', 'feasibility', 'alignment'}:
            per_participant_counts[score.participant_id] += 1

    required_respondents = len(participants)
    all_done = required_respondents > 0 and all(per_participant_counts.get(p.id, 0) >= 3 for p in participants)

    legacy_criteria = {}
    for metric_key, info in criteria.items():
        legacy_key = METRIC_TO_LEGACY_CRITERION.get(metric_key)
        if legacy_key:
            legacy_criteria[legacy_key] = info

    # Keep legacy keys stable even when there are no submissions.
    for fallback in ['valuable', 'feasible', 'applicable']:
        legacy_criteria.setdefault(fallback, {'avg': 0.0, 'count': 0, 'distribution': {str(n): 0 for n in range(1, 8)}})

    return {'criteria': legacy_criteria, 'all_done': all_done, 'required_respondents': required_respondents}


@router.post('/projects/{project_id}/decision')
def register_decision(
    project_id: int,
    payload: DecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = _ensure_owner(project_id, current_user, db)

    db.add(
        Decision(
            run_id=project_id,
            cycle=run.current_cycle,
            decision=payload.decision,
            justification=payload.justification,
        )
    )
    if payload.decision == 'pivot':
        run.current_phase = 2
        run.current_cycle = run.current_cycle + 1
    db.commit()
    return {
        'ok': True,
        'project_cycle': run.current_cycle,
        'phase': _legacy_phase_from_number(max(1, min(5, run.current_phase))),
    }


@router.post('/projects/{project_id}/summary/generate', response_model=SummaryGenerateResponse)
def generate_summary(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    run = _ensure_owner(project_id, current_user, db)
    responses = CanvasRepository(db).list_responses_by_run(project_id, cycle=run.current_cycle)
    lines = [f'- {r.content[:120]}' for r in responses[:6]]
    summary_text = f'Project: {run.title}\nSummary of LRI workshop outcomes:\n' + ('\n'.join(lines) if lines else '- No entries yet.')

    db.add(WorkshopSummary(run_id=project_id, summary_text=summary_text, highlights_json={'items': lines}))
    db.commit()

    job_id = _new_job('summarize', status='completed')
    return SummaryGenerateResponse(job_id=job_id)


@router.post('/projects/{project_id}/export/pdf', response_model=ExportOut)
def export_pdf(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    run = _ensure_owner(project_id, current_user, db)

    summary = db.query(WorkshopSummary).filter(WorkshopSummary.run_id == project_id).order_by(WorkshopSummary.id.desc()).first()
    decision = (
        db.query(Decision)
        .filter(Decision.run_id == project_id, Decision.cycle == run.current_cycle)
        .order_by(Decision.id.desc())
        .first()
    )

    responses = CanvasRepository(db).list_responses_by_run(project_id, cycle=run.current_cycle)
    question_map = {q.id: q.key for q in CanvasRepository(db).list_questions()}

    phase_data = {
        'Canvas': '\n'.join([f"{question_map.get(r.question_id, r.question_id)}: {r.content}" for r in responses])
        or 'No canvas entries.'
    }
    summary_text = summary.summary_text if summary else 'Summary not generated yet.'
    decision_text = decision.decision if decision else 'undecided'

    out_path = f'/app/exports/project_{project_id}_cycle_{run.current_cycle}.pdf'
    file_path = build_pdf(out_path, run.title, phase_data, summary_text, decision_text)

    export = Export(run_id=project_id, file_path=file_path)
    db.add(export)
    db.commit()
    db.refresh(export)

    return ExportOut(export_id=export.id, file_path=export.file_path)


@router.get('/projects/{project_id}/export/{export_id}')
def download_export(project_id: int, export_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _ensure_owner(project_id, current_user, db)

    export = db.get(Export, export_id)
    if not export or export.run_id != project_id:
        raise HTTPException(status_code=404, detail='Export not found')
    if not Path(export.file_path).exists():
        raise HTTPException(status_code=404, detail='File missing')

    return FileResponse(export.file_path, filename=Path(export.file_path).name)
