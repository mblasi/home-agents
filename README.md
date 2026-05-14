# home-agents

A local-first, privacy-preserving multi-agent AI system running entirely on a laptop — no cloud, no subscriptions, no data leaving the house.

Built on Gentoo Linux with an AMD Ryzen 9 5900HX (64GB RAM). Every component runs on CPU: speech recognition, language models, text-to-speech, and home automation control.

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
│  Microphone (44100Hz) ─── scipy resample → 16kHz                       │
│  WhatsApp audio (OGG) ─── ffmpeg → WAV 16kHz                          │
│  WhatsApp text ────────────────────────────────────────────┐           │
│  Microphone → openWakeWord "Capitán" → faster-whisper STT  │           │
└───────────────────────────────────────────┬────────────────┘           │
                                            │ POST /process               │
┌───────────────────────────────────────────▼────────────────────────────▼┐
│  CORE  :8765                                                             │
│                                                                          │
│  FastAPI ─→ Coordinator (multi-agent LLM planner)                       │
│               │                                                          │
│               ├─→ haos_agent       (Home Assistant — lights, A/C, etc.) │
│               ├─→ clima_agent      (Open-Meteo weather + alerts)        │
│               ├─→ calendar_agent   (CalDAV / Radicale)                  │
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
| Agenda | `calendar` | CalDAV (Radicale) | Active |
| Inversiones | `finance` | BCRA + Yahoo Finance + news RAG (nomic-embed-text) | Active |
| Viajes | `travel` | Documents RAG + weather | Active |
| Mapas | `maps` | Open-Meteo geocoding | Active |
| MercadoLibre | `ml` | ML API (OAuth) | Active |
| Perfil | `profile` | User context store | Active |
| Sistema | `system` | Internal diagnostics | Active |
| Usuarios | `user_mgmt` | Users + RBAC | Active |

Every agent inherits `ProactiveMixin`, enabling autonomous intent detection by scanning its own conversation history with the LLM.

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
├── backoffice/   → web admin UI at :8080
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
| STT | faster-whisper `small` int8 | Spanish, CPU, ~4.6s |
| LLM | qwen2.5:7b via Ollama | 3.5s warm, correct ACTION format |
| TTS | Piper v1.2.0 | `es_AR-daniela-high` voice, offline |
| Home automation | Home Assistant OS | REST API only, LAN |
| Audio capture | PyAudio + scipy resample | ALC256 → 44100→16000Hz |
| Agent API | FastAPI + uvicorn | :8765, POST /process |
| Backoffice | Flask | :8080, conversation explorer + agent admin |
| Coordinator | qwen2.5:7b (multi-step) | generates ExecutionPlan for parallel agent dispatch |
| Proactive | per-agent scheduler | detects patterns from history, generates intents |
| Goals | goal_store.py | discovered→planning→in_progress→completed lifecycle |
| Routines | routine_store.py | inferred behavioral patterns, candidate→active→paused lifecycle |
| Intents | intent_state.py | advise / request / goal, per-user state machine |

---

## Design decisions

- **Everything local.** No API keys, no external services (except Open-Meteo, geocoding, and ML OAuth), no telemetry.
- **CPU-only inference.** Radeon Vega 8 shares RAM and is not useful for ML. All models run on CPU with int8 quantization.
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

Phases 1–26 complete. Active development on Phase 27+.
