from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'


class RunCreate(BaseModel):
    title: str
    ai_mode_enabled: bool = True


class RunPatch(BaseModel):
    ai_mode_enabled: bool | None = None
    title: str | None = None
    problem_synthesis: str | None = None


class RunOut(BaseModel):
    id: int
    title: str
    problem_synthesis: str | None = None
    current_phase: int
    ai_mode_enabled: bool
    status: str
    current_cycle: int = 1
    decision: str | None = None
    invite_links_generated: bool = False
    created_at: datetime | None = None
    createdAt: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode='after')
    def populate_legacy_created_at(self):
        if self.createdAt is None:
            self.createdAt = self.created_at
        if self.created_at is None:
            self.created_at = self.createdAt
        return self


class RunDeleteResponse(BaseModel):
    ok: bool = True


class ParticipantOut(BaseModel):
    id: int
    project_id: int
    user_id: int | None = None
    email: str | None = None
    role: str
    created_at: datetime


class InviteCreate(BaseModel):
    role: str = 'collaborator'
    name: str | None = None


class InviteOut(BaseModel):
    invite_url: str
    expires_at: datetime


class InviteListItemOut(BaseModel):
    id: int
    name: str | None = None
    invite_url: str | None = None
    status: str
    expires_at: datetime
    created_at: datetime


class InviteInspectOut(BaseModel):
    project_id: int
    expires_at: datetime
    role: str
    status: str


class InviteAcceptRequest(BaseModel):
    email: str | None = None


class InviteAcceptResponse(BaseModel):
    participant_id: int
    project_id: int


class CanvasWriteRequest(BaseModel):
    participant_id: int
    content: str


class CanvasRecommendationsResponse(BaseModel):
    generated_count: int
    filled_count: int
    empty_count: int
    suggestions: dict[str, dict[str, str | None]]


class CanvasSingleRecommendationResponse(BaseModel):
    question_key: str
    suggested_text: str
    status: str


class Phase3OverviewResponse(BaseModel):
    generated_count: int
    field_count: int
    overviews: dict[str, str]


class Phase3SingleOverviewResponse(BaseModel):
    question_key: str
    overview_text: str


class ScoreSubmitRequest(BaseModel):
    participant_id: int
    metric_key: str
    value: int
    comment: str | None = None


class ScoreSubmitResponse(BaseModel):
    ok: bool = True


class ScoreResetResponse(BaseModel):
    ok: bool = True
    deleted_count: int = 0


# Compatibility DTOs for /projects and /invite (legacy frontend contract)
class ProjectCreate(BaseModel):
    title: str


class ProjectOut(BaseModel):
    id: int
    title: str
    current_phase: str
    current_cycle: int


class JoinInviteRequest(BaseModel):
    name: str
    company: str
    consent: bool = Field(default=False)


class JoinInviteResponse(BaseModel):
    participant_id: int
    project_id: int


class PhaseEntryPatch(BaseModel):
    actor_type: str
    actor_id: int
    field_key: str
    content: str


class PhaseEntryPatchResponse(BaseModel):
    entry_version: int
    ai_job_id: int | None = None


class AIJobStatusOut(BaseModel):
    id: int
    status: str
    job_type: str
    fallback_used: bool
    error_message: str | None = None


class AssessmentStartRequest(BaseModel):
    participants: list[int]


class AssessmentScoreRequest(BaseModel):
    actor_type: str
    actor_id: int
    criterion: str
    score: int
    justification: str | None = None


class DecisionRequest(BaseModel):
    decision: str
    justification: str | None = None


class SummaryGenerateResponse(BaseModel):
    job_id: int


class ExportOut(BaseModel):
    export_id: int
    file_path: str
