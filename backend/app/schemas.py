"""Pydantic schemas for request and response bodies."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------- auth
class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: int
    email: str
    username: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------- sessions
class SessionCreate(BaseModel):
    title: str | None = None
    model: str | None = None


class SessionUpdate(BaseModel):
    title: str | None = None
    model: str | None = None


class SessionOut(BaseModel):
    id: str
    title: str
    model: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    tool_calls_json: str | None
    citations_json: str | None
    model: str | None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------- chat
class ChatRequest(BaseModel):
    content: str = Field(min_length=1, max_length=32_000)
    model: str | None = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    use_rag: bool = True


# ---------------------------------------------------------------- documents
class DocumentOut(BaseModel):
    id: str
    filename: str
    content_type: str
    size_bytes: int
    status: str
    error: str | None
    chunk_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------- analytics
class DailyPoint(BaseModel):
    date: str
    messages: int
    tokens: int
    cost_usd: float


class ModelUsage(BaseModel):
    model: str
    messages: int
    cost_usd: float


class ToolUsage(BaseModel):
    name: str
    count: int


class AnalyticsOverview(BaseModel):
    total_messages: int
    total_sessions: int
    total_documents: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    avg_latency_ms: int
    daily: list[DailyPoint]
    models: list[ModelUsage]
    tools: list[ToolUsage]


# ---------------------------------------------------------------- meta
class AppInfo(BaseModel):
    name: str
    default_model: str
    available_models: list[str]
    rag_enabled: bool
