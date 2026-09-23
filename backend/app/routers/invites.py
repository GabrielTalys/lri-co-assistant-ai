from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models import User
from app.repositories import InviteRepository, ParticipantRepository, RunRepository
from app.schemas.common import (
    InviteAcceptRequest,
    InviteAcceptResponse,
    InviteCreate,
    InviteInspectOut,
    InviteListItemOut,
    InviteOut,
)
from app.services.invite_service import InviteService

router = APIRouter(tags=['invites'])


def _service(db: Session) -> InviteService:
    return InviteService(
        run_repo=RunRepository(db),
        invite_repo=InviteRepository(db),
        participant_repo=ParticipantRepository(db),
    )


def _invite_url_from_token(public_token: str | None) -> str | None:
    if not public_token:
        return None
    return f'{settings.frontend_public_url.rstrip("/")}/invite/{public_token}'


@router.post('/runs/{run_id}/invites', response_model=InviteOut)
@router.post('/projects/{run_id}/invites', response_model=InviteOut)
def create_invite(
    run_id: int,
    payload: InviteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = _service(db)
    try:
        raw_token, invite = svc.create_invite(
            run_id=run_id,
            owner_user_id=current_user.id,
            role=payload.role,
            invitee_name=payload.name,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if detail == 'Run not found' else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc

    db.commit()
    return InviteOut(invite_url=_invite_url_from_token(raw_token), expires_at=invite.expires_at)


@router.get('/runs/{run_id}/invites', response_model=list[InviteListItemOut])
@router.get('/projects/{run_id}/invites', response_model=list[InviteListItemOut])
def list_invites(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = _service(db)
    try:
        invites = svc.list_invites(run_id=run_id, owner_user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return [
        InviteListItemOut(
            id=invite.id,
            name=invite.participant_name or invite.invitee_name,
            invite_url=_invite_url_from_token(invite.public_token),
            status=invite.status.value,
            expires_at=invite.expires_at,
            created_at=invite.created_at,
        )
        for invite in invites
    ]


@router.get('/invites/{token}', response_model=InviteInspectOut)
def inspect_invite(token: str, db: Session = Depends(get_db)):
    svc = _service(db)
    try:
        invite = svc.inspect_invite(token)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return InviteInspectOut(
        project_id=invite.run_id,
        expires_at=invite.expires_at,
        role=invite.role,
        status=invite.status.value,
    )


@router.post('/invites/{token}/accept', response_model=InviteAcceptResponse)
def accept_invite(token: str, payload: InviteAcceptRequest, db: Session = Depends(get_db)):
    svc = _service(db)
    try:
        invite, participant = svc.accept_invite(token, email=payload.email)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.commit()
    return InviteAcceptResponse(participant_id=participant.id, project_id=invite.run_id)
