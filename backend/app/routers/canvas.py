from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import ensure_run_access, ensure_run_owner, get_optional_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.common import CanvasSingleRecommendationResponse, CanvasWriteRequest, Phase3OverviewResponse
from app.services.ai_overview_service import AIOverviewService
from app.services.ai_service import AISuggestionService
from app.services.canvas_service import CanvasService

router = APIRouter(tags=['canvas'])


@router.get('/projects/{run_id}/canvas')
def get_canvas(
    run_id: int,
    participant_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_run_access(run_id=run_id, db=db, current_user=current_user, participant_id=participant_id)
    try:
        return CanvasService(db).get_canvas_view(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post('/projects/{run_id}/canvas/overview', response_model=Phase3OverviewResponse)
def generate_phase3_overview(
    run_id: int,
    specialist_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_run_owner(run_id=run_id, db=db, current_user=current_user)
    try:
        payload = AIOverviewService(db).generate_overview(run_id, specialist_id=specialist_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.commit()
    return payload


@router.post('/projects/{run_id}/canvas/{question_key}/recommendation', response_model=CanvasSingleRecommendationResponse)
def generate_canvas_recommendation(
    run_id: int,
    question_key: str,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_run_owner(run_id=run_id, db=db, current_user=current_user)
    try:
        payload = AISuggestionService(db).generate_recommendation_for_question(run_id, question_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.commit()
    return payload


@router.put('/projects/{run_id}/canvas/{question_key}/response')
def upsert_canvas_response(
    run_id: int,
    question_key: str,
    payload: CanvasWriteRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_run_access(run_id=run_id, db=db, current_user=current_user, participant_id=payload.participant_id)
    try:
        response, question = CanvasService(db).submit_response(
            run_id=run_id,
            question_key=question_key,
            participant_id=payload.participant_id,
            content=payload.content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.commit()
    return {
        'ok': True,
        'project_id': run_id,
        'question_key': question.key,
        'participant_id': response.participant_id,
        'updated_at': response.updated_at,
    }
