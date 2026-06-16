"""Modelos Pydantic del contrato nube↔SER9. Ver fase33_cloud_backoffice.md (33.2)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

SCHEMA_VERSION = 1


class ServiceHealth(BaseModel):
    up: bool
    detail: str = ""


class CommandLatency(BaseModel):
    cmd: str
    stt_ms: int | None = None
    llm_ms: int | None = None
    haos_ms: int | None = None


class Latency(BaseModel):
    stt_ms: int | None = None
    llm_ms: int | None = None
    haos_ms: int | None = None
    by_command: list[CommandLatency] = Field(default_factory=list)


class AgentState(BaseModel):
    id: str
    active: bool
    proactive: bool = False


class RecentCommand(BaseModel):
    ts: str
    text: str
    agent: str
    ok: bool
    latency_ms: int | None = None


class WakewordNode(BaseModel):
    id: str
    ip: str | None = None
    online: bool
    rms: int | None = None


class Wakeword(BaseModel):
    last_score: float | None = None
    false_positives_24h: int | None = None
    nodes: list[WakewordNode] = Field(default_factory=list)


class UserSummary(BaseModel):
    id: str
    name: str
    role: str
    intents_pending: int = 0


class StateSnapshot(BaseModel):
    """Snapshot que el bridge envía a POST /ingest/state (allow-list de campos)."""
    schema_version: int = SCHEMA_VERSION
    ts: str
    host: str
    services: dict[str, ServiceHealth] = Field(default_factory=dict)
    latency: Latency = Field(default_factory=Latency)
    agents: list[AgentState] = Field(default_factory=list)
    recent_commands: list[RecentCommand] = Field(default_factory=list)
    wakeword: Wakeword = Field(default_factory=Wakeword)
    users_summary: list[UserSummary] = Field(default_factory=list)


class CommandRequest(BaseModel):
    """Emisión de un comando admin desde el dashboard."""
    type: str
    params: dict[str, Any] = Field(default_factory=dict)


class CommandResult(BaseModel):
    """Resultado que el bridge postea a POST /commands/{id}/result."""
    ok: bool
    output: str = ""
    error: str = ""
