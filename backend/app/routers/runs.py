from datetime import datetime
from pathlib import Path
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_optional_current_user
from app.db.session import get_db
from app.domain.canvas_keys import CANVAS_KEYS
from app.models import Decision, Export, RunStatus, User
from app.repositories import CanvasRepository, InviteRepository
from app.schemas.common import DecisionRequest, ExportOut, ParticipantOut, RunCreate, RunDeleteResponse, RunOut, RunPatch
from app.services.pdf_service import build_pdf
from app.services.run_service import PhaseAdvanceBlockedError, RunService
from app.services.score_service import ScoreService

router = APIRouter(tags=['runs'])

ALLOWED_DECISIONS = {'GO', 'ABORT', 'PIVOT'}
# Field headings of the formulated problem in the PDF report (phase 3 wording).
PDF_CANVAS_TITLES = {
    'problem': 'For the practical problem (what/how/why)',
    'stakeholders': 'Involved in the context (where/when)',
    'research_questions': 'Which bring the following implications / impacts (why)',
    'hypotheses': 'For the stakeholders (who)',
    'method': 'We have the following evidence (how)',
    'evaluation': 'And we want to investigate - objective (what/how)',
    'risks': 'Answering the following research questions (what)',
}
PDF_METRIC_LABELS = [
    ('impact', 'Value'),
    ('alignment', 'Applicability'),
    ('feasibility', 'Feasibility'),
]
EXPORTS_DIR = Path('/app/exports')


def _latest_decision_text(run_id: int, cycle: int, db: Session, *, only_final: bool = False) -> str | None:
    stmt = select(Decision.decision).where(Decision.run_id == run_id, Decision.cycle == cycle)
    if only_final:
        stmt = stmt.where(Decision.decision.in_({'GO', 'ABORT'}))
    return db.scalar(stmt.order_by(Decision.id.desc()).limit(1))


def _run_out(run, db: Session) -> dict:
    return {
        'id': run.id,
        'title': run.title,
        'problem_synthesis': run.problem_synthesis,
        'current_phase': run.current_phase,
        'ai_mode_enabled': run.ai_mode_enabled,
        'status': run.status,
        'decision': _latest_decision_text(run.id, run.current_cycle, db),
        'current_cycle': run.current_cycle,
        'created_at': run.created_at,
        'invite_links_generated': InviteRepository(db).count_by_run(run.id) > 0,
    }


def _repair_legacy_stuck_pivot_state(run, db: Session) -> bool:
    # Legacy bug recovery:
    # some runs were left in phase 5/completed with a PIVOT decision in the same cycle.
    # Correct state after pivot is phase 2, active, and next cycle.
    current_cycle_decision = _latest_decision_text(run.id, run.current_cycle, db)
    if current_cycle_decision != 'PIVOT' or run.current_phase != 5:
        return False

    run.current_phase = 2
    run.current_cycle = max(1, int(run.current_cycle or 1) + 1)
    run.status = RunStatus.ACTIVE
    run.updated_at = datetime.utcnow()
    db.flush()
    return True


def _repair_and_save(run, db: Session) -> bool:
    repaired = _repair_legacy_stuck_pivot_state(run, db)
    if repaired:
        db.commit()
        db.refresh(run)
    return repaired


def _exports_dir() -> Path:
    if EXPORTS_DIR.exists():
        return EXPORTS_DIR
    return Path(__file__).resolve().parents[3] / 'exports'


@router.post('/projects', response_model=RunOut)
def create_run(
    payload: RunCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = RunService(db).create_run(
        owner_user_id=current_user.id, title=payload.title, ai_mode_enabled=payload.ai_mode_enabled
    )
    db.commit()
    db.refresh(run)
    return _run_out(run, db)


@router.get('/projects', response_model=list[RunOut])
def list_runs(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    runs = RunService(db).list_runs(owner_user_id=current_user.id)
    repaired_any = False
    payloads = []
    for run in runs:
        repaired_any = _repair_legacy_stuck_pivot_state(run, db) or repaired_any
        payloads.append(_run_out(run, db))
    if repaired_any:
        db.commit()
    return payloads


@router.get('/projects/{run_id}', response_model=RunOut)
def get_run(
    run_id: int,
    participant_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    svc = RunService(db)
    if current_user is not None:
        try:
            run = svc.get_owned_run(run_id=run_id, owner_user_id=current_user.id)
            _repair_and_save(run, db)
            return _run_out(run, db)
        except ValueError:
            pass

    if participant_id is None:
        raise HTTPException(status_code=401, detail='Unauthorized')

    try:
        run = svc.get_run_for_participant(run_id=run_id, participant_id=participant_id)
        _repair_and_save(run, db)
        return _run_out(run, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch('/projects/{run_id}', response_model=RunOut)
def patch_run(
    run_id: int,
    payload: RunPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        run = RunService(db).update_run(
            run_id=run_id,
            owner_user_id=current_user.id,
            ai_mode_enabled=payload.ai_mode_enabled,
            title=payload.title,
            problem_synthesis=payload.problem_synthesis,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    db.refresh(run)
    return _run_out(run, db)


@router.delete('/projects/{run_id}', response_model=RunDeleteResponse)
def delete_run(run_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        RunService(db).delete_run(run_id=run_id, owner_user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return RunDeleteResponse(ok=True)


@router.post('/projects/{run_id}/advance-phase', response_model=RunOut)
def advance_phase(run_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    svc = RunService(db)
    run = svc.get_owned_run(run_id=run_id, owner_user_id=current_user.id)
    _repair_and_save(run, db)

    try:
        run = svc.advance_phase(run_id=run_id, owner_user_id=current_user.id)
    except PhaseAdvanceBlockedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    db.commit()
    db.refresh(run)
    return _run_out(run, db)


@router.post('/projects/{run_id}/decision', response_model=RunOut)
def submit_decision(
    run_id: int,
    payload: DecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    decision = (payload.decision or '').strip().upper()
    if decision not in ALLOWED_DECISIONS:
        raise HTTPException(status_code=400, detail='Decision must be GO, PIVOT, or ABORT')

    svc = RunService(db)
    run = svc.get_owned_run(run_id=run_id, owner_user_id=current_user.id)
    if _repair_and_save(run, db):
        if decision == 'PIVOT':
            return _run_out(run, db)
        raise HTTPException(status_code=409, detail='Project already pivoted and was restored to phase 2.')

    if run.current_phase != 5:
        raise HTTPException(status_code=400, detail='Decision can only be recorded in phase 5')

    if _latest_decision_text(run_id=run_id, cycle=run.current_cycle, db=db):
        raise HTTPException(status_code=409, detail='Final decision already recorded for this project.')

    decision_cycle = run.current_cycle
    try:
        if decision == 'PIVOT':
            run = svc.pivot_run(run_id=run_id, owner_user_id=current_user.id)
        else:
            run = svc.finalize_run(run_id=run_id, owner_user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.add(
        Decision(
            run_id=run_id,
            cycle=decision_cycle,
            decision=decision,
            justification=payload.justification or '',
        )
    )
    db.commit()
    db.refresh(run)
    return _run_out(run, db)


def _canvas_report_text(db: Session, run) -> str:
    canvas_repo = CanvasRepository(db)
    questions_by_id = {question.id: question for question in canvas_repo.list_questions()}

    response_by_key: dict[str, str] = {}
    title_by_key: dict[str, str] = {}
    for response in canvas_repo.list_responses_by_run(run.id, cycle=run.current_cycle):
        question = questions_by_id.get(response.question_id)
        if question is None:
            continue
        response_by_key[question.key] = (response.content or '').strip()
        title_by_key[question.key] = (question.title or '').strip()

    # Canonical fields first, in canvas order, then any field outside the canonical set.
    extra_keys = sorted(set(response_by_key) - set(CANVAS_KEYS))
    sections = []
    for key in [*CANVAS_KEYS, *extra_keys]:
        title = PDF_CANVAS_TITLES.get(key) or title_by_key.get(key) or key.replace('_', ' ').title()
        content = response_by_key.get(key, '') or 'Not provided.'
        sections.append(f'{title}\n{content}')
    return '\n\n'.join(sections)


def _assessment_report_text(db: Session, run_id: int) -> str:
    aggregates = ScoreService(db).get_aggregates(run_id=run_id)
    lines = []
    for metric_key, label in PDF_METRIC_LABELS:
        info = aggregates.get(metric_key, {})
        median = float(info.get('median', 0.0) or 0.0)
        count = int(info.get('count', 0) or 0)
        responses = f'{count} responses' if count > 0 else 'no responses'
        lines.append(f'{label}: {median:.2f} median ({responses})')
    return '\n'.join(lines)


@router.post('/projects/{run_id}/export/pdf', response_model=ExportOut)
def export_pdf(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        run = RunService(db).get_owned_run(run_id=run_id, owner_user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    latest_decision = _latest_decision_text(run_id=run.id, cycle=run.current_cycle, db=db, only_final=True)
    if latest_decision not in {'GO', 'ABORT'}:
        raise HTTPException(status_code=400, detail='Cannot export before a final decision is submitted')

    phase_data = {
        'Formulated Problem': _canvas_report_text(db, run),
        'Assessment Medians': _assessment_report_text(db, run_id),
    }
    decision_text = f'{latest_decision}\n{(run.problem_synthesis or "").strip()}'.strip()

    normalized_project_name = re.sub(r'[^a-z0-9]+', '', str(run.title or '').strip().lower()) or f'project{run_id}'
    out_path = _exports_dir() / f'{normalized_project_name}_report.pdf'
    file_path = build_pdf(str(out_path), run.title, phase_data, decision_text)

    export = Export(run_id=run_id, file_path=file_path)
    db.add(export)
    db.commit()
    db.refresh(export)
    return ExportOut(export_id=export.id, file_path=export.file_path)


@router.get('/projects/{run_id}/export/{export_id}')
def download_export(
    run_id: int,
    export_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    RunService(db).get_owned_run(run_id=run_id, owner_user_id=current_user.id)
    export = db.get(Export, export_id)
    if not export or export.run_id != run_id:
        raise HTTPException(status_code=404, detail='Export not found')
    if not Path(export.file_path).exists():
        raise HTTPException(status_code=404, detail='File missing')
    return FileResponse(export.file_path, filename=Path(export.file_path).name)


@router.get('/projects/{run_id}/participants', response_model=list[ParticipantOut])
def list_participants(run_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        participants = RunService(db).list_participants(run_id=run_id, owner_user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [
        {
            'id': p.id,
            'project_id': p.run_id,
            'user_id': p.user_id,
            'email': p.email,
            'role': p.role,
            'is_ai': p.is_ai,
            'ai_persona_role': p.ai_persona_role,
            'created_at': p.created_at,
        }
        for p in participants
    ]
