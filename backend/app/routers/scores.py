from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import ensure_run_access, get_optional_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.common import ScoreResetResponse, ScoreSubmitRequest, ScoreSubmitResponse
from app.services.score_service import ScoreService

router = APIRouter(tags=['scores'])


@router.post('/projects/{run_id}/scores', response_model=ScoreSubmitResponse)
def submit_score(
    run_id: int,
    payload: ScoreSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_run_access(run_id=run_id, db=db, current_user=current_user, participant_id=payload.participant_id)
    try:
        ScoreService(db).submit_score(
            run_id=run_id,
            participant_id=payload.participant_id,
            metric_key=payload.metric_key,
            value=payload.value,
            comment=payload.comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.commit()
    return ScoreSubmitResponse(ok=True)


@router.get('/projects/{run_id}/scores')
def get_scores(
    run_id: int,
    participant_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_run_access(run_id=run_id, db=db, current_user=current_user, participant_id=participant_id)
    svc = ScoreService(db)
    try:
        payload = {'criteria': svc.get_aggregates(run_id=run_id), **svc.get_completion(run_id=run_id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    payload['comments'] = svc.get_comments_by_participant(run_id=run_id)
    payload['ai_evaluations'] = svc.get_ai_evaluations(run_id=run_id)
    if participant_id is not None:
        try:
            payload['participant_scores'] = svc.get_participant_scores(run_id=run_id, participant_id=participant_id)
            payload['participant_comments'] = svc.get_participant_comments(run_id=run_id, participant_id=participant_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    return payload


@router.delete('/projects/{run_id}/scores/{participant_id}', response_model=ScoreResetResponse)
def reset_participant_scores(
    run_id: int,
    participant_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_run_access(run_id=run_id, db=db, current_user=current_user, participant_id=participant_id)
    try:
        deleted_count = ScoreService(db).reset_participant_scores(run_id=run_id, participant_id=participant_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return ScoreResetResponse(ok=True, deleted_count=deleted_count)
