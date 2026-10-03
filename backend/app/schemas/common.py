from datetime import datetime

from pydantic import BaseModel, Field


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


class RunDeleteResponse(BaseModel):
    ok: bool = True


class ParticipantOut(BaseModel):
    id: int
    project_id: int
    user_id: int | None = None
    email: str | None = None
    role: str
    is_ai: bool = False
    ai_persona_role: str | None = None
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


class CanvasSingleRecommendationResponse(BaseModel):
    question_key: str
    suggested_text: str
    status: str


class Phase3Perspective(BaseModel):
    specialist_id: int
    role_title: str | None = None
    overviews: dict[str, str]


class Phase3OverviewResponse(BaseModel):
    generated_count: int
    field_count: int
    overviews: dict[str, str]
    # 'default' (methodologist persona), 'specialist' (one AI specialist) or 'panel'
    # (several specialists consolidated; their individual reviews are in `perspectives`).
    mode: str = 'default'
    specialist_id: int | None = None
    role_title: str | None = None
    perspectives: list[Phase3Perspective] = Field(default_factory=list)
    failed_specialists: list[str] = Field(default_factory=list)


class AISpecialistUpsertRequest(BaseModel):
    role_title: str
    role_description: str | None = None


class AISpecialistOut(BaseModel):
    participant_id: int
    role_title: str | None = None
    role_description: str | None = None


class AISpecialistListOut(BaseModel):
    items: list[AISpecialistOut]
    max_specialists: int


class AISpecialistDeleteResponse(BaseModel):
    ok: bool = True


class AIEvaluationScoreOut(BaseModel):
    value: int
    comment: str


class AIEvaluationResponse(BaseModel):
    participant_id: int
    role_title: str | None = None
    scores: dict[str, AIEvaluationScoreOut]


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


class DecisionRequest(BaseModel):
    decision: str
    justification: str | None = None


class ExportOut(BaseModel):
    export_id: int
    file_path: str
