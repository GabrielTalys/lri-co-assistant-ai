from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_optional_current_user
from app.db.session import get_db
from app.models import User
from app.repositories import AISuggestionRepository, CanvasRepository, ParticipantRepository, RunRepository
from app.schemas.common import (
    CanvasSingleRecommendationResponse,
    CanvasRecommendationsResponse,
    CanvasWriteRequest,
    Phase3OverviewResponse,
    Phase3SingleOverviewResponse,
)
from app.services.canvas_service import CanvasService
from app.services.ai_service import AISuggestionService

router = APIRouter(tags=['canvas'])


def _service(db: Session) -> CanvasService:
    return CanvasService(
        run_repo=RunRepository(db),
        participant_repo=ParticipantRepository(db),
        canvas_repo=CanvasRepository(db),
        ai_repo=AISuggestionRepository(db),
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


def _ensure_owner_access(run_id: int, db: Session, current_user: User | None = None) -> None:
    run = RunRepository(db).get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail='Run not found')
    if current_user is None or run.owner_user_id != current_user.id:
        raise HTTPException(status_code=401, detail='Unauthorized')


@router.get('/runs/{run_id}/canvas')
@router.get('/projects/{run_id}/canvas')
def get_canvas(
    run_id: int,
    participant_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    _ensure_run_access(run_id=run_id, db=db, current_user=current_user, participant_id=participant_id)
    svc = _service(db)
    try:
        return svc.get_canvas_view(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post('/runs/{run_id}/canvas/recommendations', response_model=CanvasRecommendationsResponse)
@router.post('/projects/{run_id}/canvas/recommendations', response_model=CanvasRecommendationsResponse)
def generate_canvas_recommendations(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    _ensure_owner_access(run_id=run_id, db=db, current_user=current_user)
    try:
        payload = AISuggestionService(db).generate_recommendations_for_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.commit()
    return payload


@router.post(
    '/runs/{run_id}/canvas/{question_key}/recommendation',
    response_model=CanvasSingleRecommendationResponse,
)
@router.post(
    '/projects/{run_id}/canvas/{question_key}/recommendation',
    response_model=CanvasSingleRecommendationResponse,
)
def generate_canvas_recommendation(
    run_id: int,
    question_key: str,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    _ensure_owner_access(run_id=run_id, db=db, current_user=current_user)
    try:
        payload = AISuggestionService(db).generate_recommendation_for_question(run_id, question_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.commit()
    return payload


@router.post('/runs/{run_id}/canvas/overview', response_model=Phase3OverviewResponse)
@router.post('/projects/{run_id}/canvas/overview', response_model=Phase3OverviewResponse)
def generate_phase3_overview(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    _ensure_owner_access(run_id=run_id, db=db, current_user=current_user)
    try:
        payload = AISuggestionService(db).generate_phase3_overview(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.commit()
    return payload


@router.post('/runs/{run_id}/canvas/{question_key}/overview', response_model=Phase3SingleOverviewResponse)
@router.post('/projects/{run_id}/canvas/{question_key}/overview', response_model=Phase3SingleOverviewResponse)
def generate_phase3_canvas_overview(
    run_id: int,
    question_key: str,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    _ensure_owner_access(run_id=run_id, db=db, current_user=current_user)
    try:
        payload = AISuggestionService(db).generate_phase3_canvas_overview(run_id, question_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.commit()
    return payload


@router.patch('/runs/{run_id}/canvas/{question_key}')
@router.put('/runs/{run_id}/canvas/{question_key}')
@router.put('/runs/{run_id}/canvas/{question_key}/response')
@router.patch('/projects/{run_id}/canvas/{question_key}')
@router.put('/projects/{run_id}/canvas/{question_key}')
@router.put('/projects/{run_id}/canvas/{question_key}/response')
def upsert_canvas_response(
    run_id: int,
    question_key: str,
    payload: CanvasWriteRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    _ensure_run_access(run_id=run_id, db=db, current_user=current_user, participant_id=payload.participant_id)
    svc = _service(db)
    try:
        response, question = svc.submit_response(
            run_id=run_id,
            question_key=question_key,
            participant_id=payload.participant_id,
            content=payload.content,
            background_tasks=background_tasks,
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
