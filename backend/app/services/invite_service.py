from datetime import datetime, timedelta

from app.core.config import settings
from app.core.security import create_invite_token, hash_token
from app.models import InviteStatus
from app.repositories import InviteRepository, ParticipantRepository, RunRepository


class InviteService:
    def __init__(
        self,
        run_repo: RunRepository,
        invite_repo: InviteRepository,
        participant_repo: ParticipantRepository,
    ):
        self.run_repo = run_repo
        self.invite_repo = invite_repo
        self.participant_repo = participant_repo

    def create_invite(
        self,
        run_id: int,
        owner_user_id: int,
        role: str = 'collaborator',
        invitee_name: str | None = None,
    ):
        run = self.run_repo.get(run_id)
        if run is None or run.owner_user_id != owner_user_id:
            raise ValueError('Run not found')
        if run.current_phase != 2:
            raise ValueError('Invites can only be generated in phase 2')
        if run.current_cycle > 1:
            raise ValueError('Invites are locked after pivot and cannot be generated in follow-up cycles')

        raw_token = create_invite_token()
        normalized_name = (invitee_name or '').strip() or None
        invite = self.invite_repo.create(
            run_id=run_id,
            token_hash=hash_token(raw_token),
            public_token=raw_token,
            role=role,
            expires_at=datetime.utcnow() + timedelta(days=settings.invite_expiration_days),
            invitee_name=normalized_name,
            participant_name=normalized_name,
        )
        return raw_token, invite

    def list_invites(self, run_id: int, owner_user_id: int):
        run = self.run_repo.get(run_id)
        if run is None or run.owner_user_id != owner_user_id:
            raise ValueError('Run not found')
        return self.invite_repo.list_by_run(run_id)

    def inspect_invite(self, raw_token: str):
        invite = self.invite_repo.get_by_token_hash(hash_token(raw_token))
        if invite is None:
            raise ValueError('Invite not found. Generate a new invite link from Phase 2.')
        if invite.expires_at < datetime.utcnow():
            raise ValueError('Invite expired. Generate a new invite link from Phase 2.')
        if invite.status == InviteStatus.ACCEPTED:
            raise ValueError('Invite already used. Generate a new invite link for this participant.')
        if invite.status != InviteStatus.PENDING:
            raise ValueError('Invite is no longer active. Generate a new invite link from Phase 2.')
        return invite

    def accept_invite(self, raw_token: str, email: str | None = None):
        invite = self.inspect_invite(raw_token)
        guest_email = email or f'guest-{raw_token[:8]}@invite.local'

        participant = self.participant_repo.find_by_email(invite.run_id, guest_email)
        if participant is None:
            participant = self.participant_repo.create_with_email(invite.run_id, guest_email, role=invite.role)

        self.invite_repo.set_status(invite, InviteStatus.ACCEPTED, participant.id)
        return invite, participant
