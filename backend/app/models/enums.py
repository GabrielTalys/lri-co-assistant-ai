from enum import Enum


class RunStatus(str, Enum):
    ACTIVE = 'active'
    COMPLETED = 'completed'
    ARCHIVED = 'archived'


class InviteStatus(str, Enum):
    PENDING = 'pending'
    ACCEPTED = 'accepted'
    EXPIRED = 'expired'
    REVOKED = 'revoked'


class AISuggestionStatus(str, Enum):
    QUEUED = 'queued'
    RUNNING = 'running'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'
    STALE = 'stale'
