"""Modelos Pydantic del contrato nube↔Brain. Ver fase33_cloud_backoffice.md (33.2)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

SCHEMA_VERSION = 1
METRICS_SCHEMA_VERSION = 1


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
    kind: str = "domain"            # FASE 43: "orchestrator" para el agente raíz
    config: dict = Field(default_factory=dict)  # config efectiva (model/system_prompt/guards)


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
    # FASE 38: config vigente del panel (no PII): {screen_timeout_secs, default_dashboard}.
    # Prefila el form de "Configurar panel" en el dashboard cloud.
    config: dict[str, Any] = Field(default_factory=dict)
    # FASE 38: config REAL leída del dispositivo (heartbeat del satélite); prevalece para el prefill.
    device_config: dict[str, Any] = Field(default_factory=dict)


class Wakeword(BaseModel):
    last_score: float | None = None
    false_positives_24h: int | None = None
    status: str = "idle"   # estado del último retrain (idle/running/done/error), FASE 37.1
    nodes: list[WakewordNode] = Field(default_factory=list)


class Counts(BaseModel):
    """Conteos agregados (sin contenido PII en claro). FASE 37.1.

    El detalle (contenido de intents/goals/rutinas/conversaciones) NO sale de la LAN:
    sólo viaja el conteo, gated por `access`. El contenido queda detrás de `view_pii`
    (capacidad admin-only, 37.2) que no expone este snapshot."""
    intents: int = 0
    goals: int = 0
    routines: int = 0
    conversations: int = 0


class UserSummary(BaseModel):
    id: str
    name: str
    role: str
    intents_pending: int = 0
    email: str | None = None   # login_email (identidad de acceso al dashboard), FASE 33.19


class Dashboard(BaseModel):
    """Dashboard de HA (lovelace) para el selector de 'dashboard por defecto' de un panel
    (FASE 38). `url` es el deeplink que abre la HA Companion."""
    title: str
    url_path: str
    url: str


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
    # FASE 37.1: alertas proactivas (texto listo para TTS; gated por `access`, no PII secreta)
    # y conteos agregados de intents/goals/rutinas/conversaciones (sin contenido en claro).
    alerts: list[str] = Field(default_factory=list)
    counts: Counts = Field(default_factory=Counts)
    # FASE 38: dashboards de HA para poblar el selector del comando panel.config (no PII).
    dashboards: list[Dashboard] = Field(default_factory=list)
    # FASE 43: modelos LLM disponibles en Ollama, para poblar el selector del comando agent.config.
    models: list[str] = Field(default_factory=list)
    # Matriz unificada de targets (34.15): {targets: [{id,label,where,kind,version,url,latest,
    # latest_url,behind,command,params,advanced}], satellite_expected}. Opcional (retrocompat).
    versions: dict[str, Any] = Field(default_factory=dict)


class MetricsSnapshot(BaseModel):
    """Agregados de métricas que el bridge envía a POST /ingest/metrics (FASE 35.5).

    Los agregados se calculan en el Brain (core, FASE 35.2/35.3); la nube sólo almacena
    y muestra. Campos flexibles (dict/list) con el shape que devuelve la API del core."""
    schema_version: int = METRICS_SCHEMA_VERSION
    ts: str
    window_hours: int = 24
    voice_summary: dict[str, Any] = Field(default_factory=dict)
    voice_series: dict[str, Any] = Field(default_factory=dict)
    voice_conf_series: dict[str, Any] = Field(default_factory=dict)   # FASE 37.12 (voice-id vs threshold)
    ww_score_series: dict[str, Any] = Field(default_factory=dict)     # FASE 37.11 (score WW vs threshold)
    retrains: list[dict[str, Any]] = Field(default_factory=list)
    llm_summary: dict[str, Any] = Field(default_factory=dict)
    llm_by_model: list[dict[str, Any]] = Field(default_factory=list)
    llm_by_agent: list[dict[str, Any]] = Field(default_factory=list)
    llm_series: dict[str, Any] = Field(default_factory=dict)
    continuity_summary: dict[str, Any] = Field(default_factory=dict)  # FASE 36.10
    continuity_series: dict[str, Any] = Field(default_factory=dict)   # FASE 36.10


class CommandRequest(BaseModel):
    """Emisión de un comando admin desde el dashboard."""
    type: str
    params: dict[str, Any] = Field(default_factory=dict)


class CommandResult(BaseModel):
    """Resultado que el bridge postea a POST /commands/{id}/result."""
    ok: bool
    output: str = ""
    error: str = ""


class CommandProgress(BaseModel):
    """Líneas de log en vivo que el bridge postea a POST /commands/{id}/progress (D5)."""
    lines: list[str] = Field(default_factory=list)
