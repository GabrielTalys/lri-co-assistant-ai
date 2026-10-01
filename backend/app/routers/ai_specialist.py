from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_optional_current_user
from app.db.session import get_db
from app.models import User
from app.repositories import InviteRepository, ParticipantRepository, RunRepository, ScoreRepository
from app.schemas.common import (
    AIEvaluationResponse,
    AISpecialistDeleteResponse,
    AISpecialistOut,
    AISpecialistUpsertRequest,
)
from app.services.ai_evaluation_service import AIEvaluationService
from app.services.ai_specialist_service import AISpecialistService

router = APIRouter(tags=['ai-specialist'])


def _service(db: Session) -> AISpecialistService:
    return AISpecialistService(
        run_repo=RunRepository(db),
        participant_repo=ParticipantRepository(db),
        score_repo=ScoreRepository(db),
    )


def _ensure_run_access(
    run_id: int,
    db: Session,
    current_user: User | None = None,
    participant_id: int | None = None,
) -> None:
    run = RunRepository(db).get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail='Run not found')
    if current_user is not None and run.owner_user_id == current_user.id:
        return
    if participant_id is None:
        raise HTTPException(status_code=401, detail='Unauthorized')
    participant = ParticipantRepository(db).get(participant_id)
    if participant is None or participant.run_id != run_id:
        raise HTTPException(status_code=404, detail='Run not found')


def _to_out(participant) -> AISpecialistOut:
    if participant is None:
        return AISpecialistOut(is_configured=False)
    return AISpecialistOut(
        is_configured=True,
        participant_id=participant.id,
        role_title=participant.ai_persona_role,
        role_description=participant.ai_persona_description,
    )


@router.put('/runs/{run_id}/ai-specialist', response_model=AISpecialistOut)
@router.put('/projects/{run_id}/ai-specialist', response_model=AISpecialistOut)
def upsert_ai_specialist(
    run_id: int,
    payload: AISpecialistUpsertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = _service(db)
    try:
        participant = svc.upsert(
            run_id=run_id,
            owner_user_id=current_user.id,
            role_title=payload.role_title,
            role_description=payload.role_description,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if detail == 'Run not found' else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc

    db.commit()
    return _to_out(participant)


@router.get('/runs/{run_id}/ai-specialist', response_model=AISpecialistOut)
@router.get('/projects/{run_id}/ai-specialist', response_model=AISpecialistOut)
def get_ai_specialist(
    run_id: int,
    participant_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    _ensure_run_access(run_id=run_id, db=db, current_user=current_user, participant_id=participant_id)
    svc = _service(db)
    return _to_out(svc.get_config(run_id))


@router.delete('/runs/{run_id}/ai-specialist', response_model=AISpecialistDeleteResponse)
@router.delete('/projects/{run_id}/ai-specialist', response_model=AISpecialistDeleteResponse)
def delete_ai_specialist(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = _service(db)
    try:
        svc.remove(run_id=run_id, owner_user_id=current_user.id)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if detail == 'Run not found' else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc

    db.commit()
    return AISpecialistDeleteResponse(ok=True)


@router.post('/runs/{run_id}/ai-specialist/evaluate', response_model=AIEvaluationResponse)
@router.post('/projects/{run_id}/ai-specialist/evaluate', response_model=AIEvaluationResponse)
def evaluate_ai_specialist(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        payload = AIEvaluationService(db).generate_ai_evaluation(
            run_id=run_id, owner_user_id=current_user.id
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if detail == 'Run not found' else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc

    db.commit()
    return AIEvaluationResponse(**payload)
