from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_optional_current_user
from app.db.session import get_db
from app.models import User
from app.repositories import InviteRepository, ParticipantRepository, RunRepository, ScoreRepository
from app.schemas.common import ScoreResetResponse, ScoreSubmitRequest, ScoreSubmitResponse
from app.services.score_service import ScoreService

router = APIRouter(tags=['scores'])


def _service(db: Session) -> ScoreService:
    return ScoreService(
        run_repo=RunRepository(db),
        participant_repo=ParticipantRepository(db),
        score_repo=ScoreRepository(db),
        invite_repo=InviteRepository(db),
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


@router.post('/runs/{run_id}/scores', response_model=ScoreSubmitResponse)
@router.post('/projects/{run_id}/scores', response_model=ScoreSubmitResponse)
def submit_score(
    run_id: int,
    payload: ScoreSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    _ensure_run_access(run_id=run_id, db=db, current_user=current_user, participant_id=payload.participant_id)
    svc = _service(db)
    try:
        svc.submit_score(
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


@router.get('/runs/{run_id}/scores')
@router.get('/projects/{run_id}/scores')
def get_scores(
    run_id: int,
    participant_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    _ensure_run_access(run_id=run_id, db=db, current_user=current_user, participant_id=participant_id)
    svc = _service(db)
    try:
        criteria = svc.get_aggregates(run_id=run_id)
        completion = svc.get_completion(run_id=run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    payload = {'criteria': criteria, **completion}
    payload['comments'] = svc.get_comments_by_participant(run_id=run_id)
    if participant_id is not None:
        try:
            payload['participant_scores'] = svc.get_participant_scores(run_id=run_id, participant_id=participant_id)
            payload['participant_comments'] = svc.get_participant_comments(run_id=run_id, participant_id=participant_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    return payload


@router.delete('/runs/{run_id}/scores/{participant_id}', response_model=ScoreResetResponse)
@router.delete('/projects/{run_id}/scores/{participant_id}', response_model=ScoreResetResponse)
def reset_participant_scores(
    run_id: int,
    participant_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    _ensure_run_access(run_id=run_id, db=db, current_user=current_user, participant_id=participant_id)
    svc = _service(db)
    try:
        deleted_count = svc.reset_participant_scores(run_id=run_id, participant_id=participant_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return ScoreResetResponse(ok=True, deleted_count=deleted_count)
