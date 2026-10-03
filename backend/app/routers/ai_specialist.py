from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import ensure_run_access, get_current_user, get_optional_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.common import (
    AIEvaluationResponse,
    AISpecialistDeleteResponse,
    AISpecialistListOut,
    AISpecialistOut,
    AISpecialistUpsertRequest,
)
from app.services.ai_evaluation_service import AIEvaluationService
from app.services.ai_specialist_service import MAX_AI_SPECIALISTS, AISpecialistService

router = APIRouter(tags=['ai-specialist'])


def _http_error(exc: ValueError) -> HTTPException:
    detail = str(exc)
    status_code = 404 if detail in {'Run not found', 'AI specialist not found'} else 400
    return HTTPException(status_code=status_code, detail=detail)


def _to_out(participant) -> AISpecialistOut:
    return AISpecialistOut(
        participant_id=participant.id,
        role_title=participant.ai_persona_role,
        role_description=participant.ai_persona_description,
    )


@router.get('/projects/{run_id}/ai-specialists', response_model=AISpecialistListOut)
def list_ai_specialists(
    run_id: int,
    participant_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_run_access(run_id=run_id, db=db, current_user=current_user, participant_id=participant_id)
    specialists = AISpecialistService(db).list_specialists(run_id)
    return AISpecialistListOut(
        items=[_to_out(specialist) for specialist in specialists],
        max_specialists=MAX_AI_SPECIALISTS,
    )


@router.post('/projects/{run_id}/ai-specialists', response_model=AISpecialistOut)
def create_ai_specialist(
    run_id: int,
    payload: AISpecialistUpsertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        participant = AISpecialistService(db).create(
            run_id=run_id,
            owner_user_id=current_user.id,
            role_title=payload.role_title,
            role_description=payload.role_description,
        )
    except ValueError as exc:
        raise _http_error(exc) from exc

    db.commit()
    return _to_out(participant)


@router.put('/projects/{run_id}/ai-specialists/{specialist_id}', response_model=AISpecialistOut)
def update_ai_specialist(
    run_id: int,
    specialist_id: int,
    payload: AISpecialistUpsertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        participant = AISpecialistService(db).update(
            run_id=run_id,
            owner_user_id=current_user.id,
            specialist_id=specialist_id,
            role_title=payload.role_title,
            role_description=payload.role_description,
        )
    except ValueError as exc:
        raise _http_error(exc) from exc

    db.commit()
    return _to_out(participant)


@router.delete('/projects/{run_id}/ai-specialists/{specialist_id}', response_model=AISpecialistDeleteResponse)
def delete_ai_specialist(
    run_id: int,
    specialist_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        AISpecialistService(db).remove(run_id=run_id, owner_user_id=current_user.id, specialist_id=specialist_id)
    except ValueError as exc:
        raise _http_error(exc) from exc

    db.commit()
    return AISpecialistDeleteResponse(ok=True)


@router.post('/projects/{run_id}/ai-specialists/{specialist_id}/evaluate', response_model=AIEvaluationResponse)
def evaluate_ai_specialist(
    run_id: int,
    specialist_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        payload = AIEvaluationService(db).generate_ai_evaluation(
            run_id=run_id, owner_user_id=current_user.id, specialist_id=specialist_id
        )
    except ValueError as exc:
        raise _http_error(exc) from exc

    db.commit()
    return AIEvaluationResponse(**payload)
