# home-agents

A local-first, privacy-preserving multi-agent AI system running entirely on a home server — no cloud, no subscriptions, no data leaving the house.

Runs on the **Brain** (Beelink SER9 Pro — AMD Ryzen 7 255, 27 GiB RAM, Radeon 780M / ROCm) under Debian 13 Trixie · Proxmox VE 9.2.2. Speech recognition, language models, text-to-speech, and home automation control all run on the LAN, with the LLM accelerated on the integrated GPU via ROCm. A laptop serves as the development environment.

---

## What it does

You say **"Capitán"** → the system wakes up → listens → understands → acts → speaks back.

Multiple channels are supported:

| Channel | Trigger | Response |
|---------|---------|----------|
| Voice (mic) | "Capitán" wake word | Piper TTS spoken reply |
| WhatsApp text | Inbound message to authorized number | WhatsApp text reply |
| WhatsApp audio | Voice note PTT | WhatsApp text reply |

Beyond reactive commands, the system also runs **proactively**: each agent periodically scans its own history and context to detect user patterns and generate intents autonomously.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  INPUT                                                                  │
│  NSPanel node (satellite.py) → openWakeWord "Capitán" → record command │
│       │ POST /process-audio (WAV)   ◄── follow-up turns: if agent asks  │
│       │ X-Needs-Reply → reopen mic WITHOUT re-wake (conversation_id)     │
│  ┌────▼──────────────────────────────────────────────────────────┐     │
│  │ AUDIO SERVER :8766 (Brain) — STT (faster-whisper) + voice-id    │     │
│  │ speaker_id gate (TV/guest → drop) → core → Piper TTS → WAV     │     │
│  └────┬──────────────────────────────────────────────────────────┘     │
│  WhatsApp audio/text ──────────────────────────────────────┐           │
└───────────────────────────────────────────┬────────────────┘           │
                                            │ POST /process               │
┌───────────────────────────────────────────▼────────────────────────────▼┐
│  CORE  :8765                                                             │
│                                                                          │
│  FastAPI ─→ Coordinator (multi-agent LLM planner)                       │
│               │                                                          │
│               ├─→ haos_agent       (Home Assistant — lights, A/C, etc.) │
│               ├─→ clima_agent      (Open-Meteo weather + alerts)        │
│               ├─→ calendar_agent   (Google Calendar)                    │
│               ├─→ finance_agent    (portfolio, BCRA, MercadoLibre)      │
│               ├─→ travel_agent     (documents, itinerary, alerts)       │
│               ├─→ maps_agent       (Open-Meteo geocoding + directions)  │
│               ├─→ ml_agent         (MercadoLibre search & price track)  │
│               ├─→ profile_agent    (user preferences & onboarding)      │
│               ├─→ system_agent     (health, status, diagnostics)        │
│               └─→ user_mgmt_agent  (CRUD users, RBAC, enrollment)       │
│                                                                          │
│  ProactiveScheduler ─→ runs each agent's proactive_check() on schedule  │
│  GoalEngine ─→ reviews pending goals, invokes agents to advance them    │
│  RoutineDetector ─→ infers behavioral patterns from interaction history  │
│  IntentState ─→ tracks advise/request/goal lifecycle per user           │
└──────────────────────────────────────────┬───────────────────────────────┘
                                           │
           ┌───────────────────────────────┼───────────────────────────────┐
           ▼                               ▼                               ▼
    Home Assistant OS              Piper TTS + ffplay              WhatsApp reply
    REST :8123                     spoken response                 wa_notifier.py
    (lights, A/C, blinds…)
```

---

## Agents

| Agent | ID | Source | Status |
|-------|----|--------|--------|
| Domótica | `haos` | Home Assistant REST | Active |
| Clima | `clima` | Open-Meteo API | Active |
| Agenda | `calendar` | Google Calendar (CalDAV, App Password) | Active |
| Inversiones | `finance` | BCRA + Yahoo Finance + news RAG (nomic-embed-text) | Active |
| Viajes | `travel` | Documents RAG + weather | Active |
| Mapas | `maps` | Open-Meteo geocoding | Active |
| MercadoLibre | `ml` | ML API (OAuth) | Active |
| Perfil | `profile` | User context store | Active |
| Sistema | `system` | Internal diagnostics | Active |
| Usuarios | `user_mgmt` | Users + RBAC | Active |

Every agent inherits `ProactiveMixin`, enabling autonomous intent detection by scanning its own conversation history with the LLM.

---

## Recursive agent runtime (Phase 41 — built, deployed dormant)

Phase 41 unifies the whole system under **one recursive agent abstraction** (`core/agent_runtime.py`,
`RecursiveAgent`): every agent *is* an orchestrator. Its `process()` runs an LLM↔tools loop — the
agent's tools are backend interactions; delegating to an affine sub-agent is the recursive
`call_agent(agent_id, query)` tool; the loop's final turn is the consolidated answer. Channel
housekeeping (close / ignore / capture-reply / clarify) are **tools of the root agent**, so "chau"
closing a conversation is an organic LLM decision, not a keyword. No deterministic pre-planner
short-circuits, no `fast_classifier`. Guards (max depth/iters, global LLM-call budget, cycle set)
keep the tree bounded. All 10 domain agents expose a `build_recursive()` view; tree-level metrics
(LLM calls / tool calls / depth per request) feed `/metrics/llm/runtime`. Latency optimizations
(Phase 42): skip the consolidation turn on single-child delegation, per-tier model (`AGENT_LEAF_MODEL`),
and a non-binding routing hint from the classifier.

**Status: ACTIVE in production** (`AGENT_RUNTIME_RECURSIVE=true` in `core/.env` on the Brain since
2026-06-23). The recursive tree serves all traffic on a single `qwen2.5:7b`; routing, delegation and
housekeeping work end-to-end. Each domain query costs ~14 s vs ~5 s on the old coordinator path
because the tree multiplies LLM calls — accepted trade-off for fully organic orchestration. The
Phase 9 coordinator path remains as a fallback (revert = set the flag OFF and restart `capitan-core`).
The per-tier model lever (small model on leaves, `AGENT_LEAF_MODEL`) is **not usable on the current
iGPU** (Radeon 780M / ROCm): a qwen3 8b+4b pair exceeds the ~8 GB GTT ceiling and won't load; a
qwen2.5 7b+3b pair loads but the leaf's tool-constrained generation aborts intermittently — so the
tree runs single-model. A dedicated GPU would unlock the tier and cut latency.

**Orchestrator as a first-class agent (Phase 43).** The root agent is no longer a hardcoded runtime
construct: it lives in the catalog (`agent_registry.get_catalog()` = domain `get_registry()` + a
synthetic `orchestrator` entry of `kind="orchestrator"` — not delegable, not proactive, not
disableable) and its config (LLM `model`, `system_prompt`, and guards `max_iters`/`max_depth`/
`llm_budget`/`routing_hint_enabled`) lives in `agent_config`, hot-editable like any agent.
`build_root_agent` reads it; the per-agent model now wins over the global `AGENT_LEAF_MODEL` env
(generalizing Phase 42's env-only tier). It's editable from both backoffices: the local one shows it
in `/agents` with an edit form; the cloud one with the typed `agent.config` command (model picker fed
by `GET /models` via the snapshot).

---

## Conversation continuity (Phase 36)

Continuity is unified across channels rather than patched per channel. A `Conversation`
(`core/conversations.py`) is channel-aware: the inactivity TTL is per channel (voice ~120s,
WhatsApp 6h), and `ContinuationState` models "awaiting the user's reply" (`clarification` /
`field` / `reply`) as one persisted state exposed on every response.

- **WhatsApp resumes by recency** — a new inbound message reopens the sender's latest vigent
  conversation instead of starting a fresh one on a time gap.
- **Proactive notifications are turns** — delivering an advise/goal/request seeds an `assistant`
  turn tied to its `intent_id`; the user's reply (quoted or by recency) lands in that conversation
  and routes to the owner agent.
- **The greeting is per session** — the recognition greeting (`greeting.py`) is prepended once
  per user/channel session (`greeted_at` + cooldown), not on every conversation.
- **Multi-turn history reaches the LLM** — the recursive hot-path records each turn so
  `conv.context()` carries the prior turns to the model on the next request.
- **Continuity metrics** (turns/conv, multi-turn %, sustained follow-ups, proactive replies) are
  exposed at `GET /metrics/continuity/*` and charted in both backoffices.

The full cross-channel cycle is covered e2e in `core/tests/test_continuity_e2e.py`; only the
on-device voice verification with the physical NSPanel remains (36.6).

---

## Observability (Phase 35)

Voice and LLM metrics are centralized in SQLite by `core/metrics_store.py`, separate from
the per-request traces:

- **Voice** — every wake-word event (TP/FP with reason, voice-id, latencies) is pushed by the
  audio server to `POST /metrics/voice/event`; retrains are recorded from `/wakeword/train`.
- **LLM** — derived from each `RequestTrace` at close time into `llm_calls` / `agent_steps` /
  `request_metrics` (latencies by model/agent, tokens, tool calls, coordinator latency,
  success/fallback rates) without duplicating the trace.

The core exposes a read-only metrics API (`GET /metrics/{voice,llm}/*`: summaries, time
series as `{labels, series}`, by-model, by-agent, retrains) with range/model/agent/node
filters. The **local backoffice** renders it at `/metrics` (Chart.js, filters, auto-refresh);
the **cloud backoffice** shows an equivalent view, fed by the egress-only bridge that pushes
aggregates to `POST /ingest/metrics` and gated by the FASE 33 RBAC. Both also chart **wake-word
score** and **voice-id confidence** against their thresholds over time (FASE 37).

The cloud backoffice (FASE 37) is a **mobile-first SPA** with a sidebar (Monitoreo / Sistema /
Administración), hash router and per-capability gating, with full parity with the local
backoffice for everything that's safe to expose egress-only. Its command UI is end-user grade:
contextual actions per entity and typed forms rendered from `/api/catalog` (no raw JSON). A new
admin-only `view_pii` capability gates content (command text); the snapshot only carries counts.

---

## Repositories

| Repo | Purpose |
|------|---------|
| [`home-agents`](https://github.com/mblasi/home-agents) | Umbrella — masterplan, scripts, submodules |
| [`home-agents-ear`](https://github.com/mblasi/home-agents-ear) | Audio: mic, wake word, STT, TTS, dashboard |
| [`home-agents-core`](https://github.com/mblasi/home-agents-core) | Agent logic: FastAPI :8765, LLM dispatch, all agents |

```
home-agents/
├── ear/          → submodule: home-agents-ear
├── core/         → submodule: home-agents-core
├── backoffice/   → web admin UI at :8080 (LAN)
├── cloud/        → cloud backoffice (Cloud Run + Firestore) + bridge (egress-only)
├── masterplan/   → estado.md (task list + decisions + functional docs)
├── scripts/      → sync_issues.py, lint_estado.py
└── interagent/   → product concept (Interagent network)
```

---

## Quick start

```zsh
# Clone with submodules
git clone --recurse-submodules git@github.com:mblasi/home-agents.git ~/workspace/home-agents

# Configure credentials
cp ~/workspace/home-agents/core/.env.example ~/workspace/home-agents/core/.env
# Fill in: HAOS_URL, HAOS_TOKEN, OLLAMA_URL, CORE_PORT=8765

# Activate Python environment
source ~/home-agents-env/bin/activate

# Start core, then ear
systemctl --user start capitan-core   # FastAPI :8765
systemctl --user start capitan        # audio pipeline

# Or interactively with dashboard
cd ~/workspace/home-agents/core && uvicorn server:app --host 127.0.0.1 --port 8765
bash ~/workspace/home-agents/ear/dashboard.sh
```

---

## Stack

| Layer | Tool | Notes |
|-------|------|-------|
| Wake word | openWakeWord (custom trained) | "Capitán", ONNX, threshold 0.8 |
| STT | faster-whisper `small` int8 | Spanish, ~4.6s |
| LLM | qwen2.5:7b via Ollama | ROCm (Radeon 780M), ~3-5s warm, correct ACTION format |
| TTS | Piper v1.2.0 | `es_AR-daniela-high` voice, offline |
| Home automation | Home Assistant OS | REST API only, LAN |
| Audio nodes | NSPanel Pro (satellite.py) | wake word + mic/speaker per room |
| Audio server | FastAPI + uvicorn | :8766, STT/TTS + voice-id + enrollment channel |
| Voice-ID | resemblyzer (GE2E) | server-side speaker gate (TV/guest → drop) |
| Agent API | FastAPI + uvicorn | :8765, POST /process |
| Backoffice | FastAPI + HTMX | :8080, users/agents/wake word/panels (config: screen-off + dashboard)/ambientes/provisioning |
| Coordinator | qwen2.5:7b (multi-step) | generates ExecutionPlan for parallel agent dispatch |
| Proactive | per-agent scheduler | detects patterns from history, generates intents |
| Goals | goal_store.py | discovered→planning→in_progress→completed lifecycle |
| Routines | routine_store.py | inferred behavioral patterns, candidate→active→paused lifecycle |
| Intents | intent_state.py | advise / request / goal, per-user state machine |

---

## Design decisions

- **Everything local.** No API keys, no external services (except Open-Meteo, geocoding, and ML OAuth), no telemetry.
- **GPU-accelerated inference on the Brain.** qwen2.5:7b runs on Ollama with ROCm on the Radeon 780M (RDNA 3 / gfx1103, `HSA_OVERRIDE_GFX_VERSION=11.0.0`), ~3-5s warm vs ~27.5s CPU-only. STT/TTS run with int8 quantization.
- **ear ↔ core over HTTP.** Separating audio I/O from agent logic via a REST boundary allows multiple `ear` instances (rooms, WhatsApp) to share one `core`.
- **Audio resampling.** ALC256 doesn't support 16kHz. Captured at 44100Hz, resampled with `scipy.signal.resample_poly` (up=160, down=441).
- **qwen2.5:7b.** phi3:mini too slow (24.8s), phi3-ha invented entity IDs. qwen2.5:7b gives consistent ACTION format in 3.5s.
- **Piper offline TTS.** Four Spanish/Argentine voice models, fully offline.
- **ffplay over aplay.** aplay requires explicit format parameters with this soundcard.
- **Multi-agent coordinator.** Single-agent dispatch replaced by LLM-planned ExecutionPlan, supporting parallel and sequential steps across agents.
- **Proactive intents.** Agents autonomously scan their own history to detect patterns (forgetting to water plants, frequent price checks, upcoming events), generating advise/request/goal intents without being asked.

---

## Status

See [`masterplan/estado.md`](masterplan/estado.md) for the full task list and decisions.
See [`masterplan/arquitectura_funcional.md`](masterplan/arquitectura_funcional.md) for the detailed functional documentation.

Phases 1–40 complete and in production. Phase 41 (recursive agent runtime) + Phase 42 (latency
optimizations) are **active in production** (`AGENT_RUNTIME_RECURSIVE=true` on the Brain) — the
recursive agent tree now serves all traffic; the Phase 9 coordinator path remains as a fallback.
See "Recursive agent runtime" above.
