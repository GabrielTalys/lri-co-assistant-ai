from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User
from app.repositories import ParticipantRepository, RunRepository

security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Missing token')
    user_id = decode_access_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token')
    user = db.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='User not found')
    return user


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)
) -> User | None:
    if not credentials:
        return None
    user_id = decode_access_token(credentials.credentials)
    if not user_id:
        return None
    return db.get(User, int(user_id))


def ensure_run_access(
    run_id: int,
    db: Session,
    current_user: User | None = None,
    participant_id: int | None = None,
) -> None:
    """Let through the run owner, or a guest identified by one of the run's participants."""
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


def ensure_run_owner(run_id: int, db: Session, current_user: User | None = None) -> None:
    run = RunRepository(db).get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail='Run not found')
    if current_user is None or run.owner_user_id != current_user.id:
        raise HTTPException(status_code=401, detail='Unauthorized')
