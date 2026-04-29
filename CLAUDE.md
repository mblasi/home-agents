# CLAUDE.md — home-agents

Red de agentes de IA local-first para domótica, clima, agenda, inversiones y viajes.
Todo corre en la laptop. Nada sale de la red local.

## Plan y estado

El plan vive en `masterplan/estado.md`. Al iniciar sesión, leerlo para saber en qué fase
estamos y cuál es el próximo paso. Las tareas completadas tienen issues cerrados en GitHub;
las pendientes tienen issues abiertos en https://github.com/mblasi/home-agents.

Para sincronizar estado del plan con los issues de GitHub:
```
python scripts/sync_issues.py           # aplica cambios
python scripts/sync_issues.py --dry-run # solo muestra qué haría
```

## Hardware

```
CPU:  AMD Ryzen 9 5900HX — 8 cores / 16 threads — znver3
GPU:  Radeon Vega 8 integrada — comparte RAM — NO útil para ML
RAM:  64GB DDR4
OS:   Gentoo Linux — GCC 15.2.1 znver3 — kernel x86_64
```

Toda la inferencia corre en CPU con cuantización int8. No intentar usar la GPU.

## Entorno Python

```zsh
source ~/ai-env/bin/activate   # siempre activar antes de correr cualquier script
```

- Python 3.13.12, pip 26.0.1, uv 0.11.8
- El venv está en `~/ai-env`, NO en el repo
- `pyyaml` está instalado en el venv

## Audio — restricciones críticas

La placa ALC256 **no soporta 16kHz**. Solo acepta 44100Hz y 48000Hz.

```
Captura:    pyaudio, device_index=4 (HD-Audio Generic: ALC256 Analog hw:1,0)
Frecuencia: 44100Hz → resamplear a 16000Hz con scipy.signal.resample_poly
Ratio:      up=160, down=441
```

Reproducción de WAV: usar **ffplay**, no aplay.
```zsh
ffplay -autoexit -nodisp archivo.wav
```
`aplay` falla sin parámetros explícitos de formato con este hardware.

## Stack de inferencia

### Ollama
```
Servicio:   localhost:11434
Versión:    0.20.3 (vulkan + AVX2 + FMA3 + F16C)
Modelo:     qwen2.5:7b  ← MODELO PRINCIPAL (3.5s warm, formato ACTION correcto)
Descartados: phi3:mini (24.8s), phi3-ha (inventa entity_ids)
```

### faster-whisper
```
Modelo:  small (cache HuggingFace)
Device:  cpu, compute_type=int8, language=es
Latencia: ~4.6s para 5s de audio
```

### Piper TTS
```
Binario: ~/.local/bin/piper/piper  (v1.2.0)
Voces:   ~/.local/share/piper/
  es_AR-daniela-high.onnx    ← voz del agente (wake word + respuestas)
  es_MX-claude-high.onnx     ← descartada
  es_ES-davefx-medium.onnx   ← descartada
  es_ES-sharvard-medium.onnx ← diversidad en training
Sample rate: 22050Hz
```

### openWakeWord
```
Repo:   ~/ai-lab/ear/wakeword/openWakeWord/
Data:   ~/ai-lab/ear/wakeword/data/capitán/positive/  (90 samples WAV, voz daniela)
        ~/ai-lab/ear/wakeword/data/capitán/negative/
Wake word objetivo: "Capitán"
```

Parche aplicado (no revertir):
`acoustics/directivity.py` — `sph_harm` → `sph_harm_y` (scipy 1.17.1 / Python 3.13)

## Home Assistant OS (HAOS)

```
Acceso:    http://192.168.68.101:8123
Estrategia: HAOS solo recibe órdenes via REST API
            Todo el procesamiento (STT/LLM/TTS) corre en la laptop
Token:     en core/.env (excluido del repo)
Cliente:   core/ha_client.py — get_state / call_service / ENTITIES map
```

## Estructura del repo

```
home-agents/              ← repo umbrella (este repo)
├── ear/                  ← submodule: github.com/mblasi/home-agents-ear
│   ├── listen.py         loop principal: wake word → STT → HTTP/core → TTS
│   ├── tts.py            Piper TTS → ffplay (voz daniela)
│   ├── panel_*.py        paneles Rich para zellij dashboard
│   ├── dashboard.sh/kdl  lanzador del dashboard interactivo
│   ├── run.sh            wrapper para systemd
│   ├── capitan.service   unit file (instalar en ~/.config/systemd/user/)
│   └── wakeword/         datos de training y submodule openWakeWord
│
├── core/                 ← submodule: github.com/mblasi/home-agents-core
│   ├── server.py         FastAPI en :8765 — POST /process, GET /agents, GET /health
│   ├── agent.py          texto → qwen2.5:7b → parse ACTION → ha_client
│   ├── agent_registry.py dispatcher + REGISTRY de agentes
│   ├── ha_client.py      cliente REST HAOS + mapa de entidades
│   └── capitan-core.service  unit file para el servidor
│
├── masterplan/
│   ├── estado.md         plan completo con estado, latencias y decisiones
│   └── issues.yaml       mapeo task_id → GitHub issue number
│
├── scripts/
│   └── sync_issues.py    sincroniza estado.md con GitHub issues
│
└── interagent/           concepto del producto Interagent (red de redes de agentes)
```

## Configuración (.env)

Cada submodule tiene su propio `.env` (gitignored):

**`core/.env`**:
```
HAOS_URL=http://192.168.68.101:8123
HAOS_TOKEN=eyJ...
OLLAMA_URL=http://localhost:11434
CORE_PORT=8765
```

**`ear/.env`**:
```
CORE_URL=http://localhost:8765
CORE_TIMEOUT=30
```

## Comandos frecuentes

```zsh
# Activar entorno
source ~/ai-env/bin/activate

# Correr el core (debe estar antes que ear)
cd ~/ai-lab/core
uvicorn server:app --host 127.0.0.1 --port 8765

# Correr el agente (pipeline completo)
bash ~/ai-lab/ear/dashboard.sh          # dashboard interactivo
systemctl --user start capitan-core     # core como servicio
systemctl --user start capitan          # ear como servicio
systemctl --user stop capitan-core
systemctl --user stop capitan
journalctl --user -u capitan -f         # logs ear
journalctl --user -u capitan-core -f    # logs core

# Test del core
curl http://localhost:8765/health
curl -X POST http://localhost:8765/process \
  -H 'Content-Type: application/json' \
  -d '{"text":"prende la luz"}'

# Debug wake word scores en tiempo real
python ~/ai-lab/ear/wakeword/debug_scores.py

# Test TTS
python ~/ai-lab/ear/tts.py

# Test parser LLM + HA (directo, sin servidor)
python ~/ai-lab/core/agent.py

# Sync issues con GitHub
python scripts/sync_issues.py

# Actualizar submodules
git submodule update --remote
```

## Pipeline actual

```
[MIC hw:1,0 44100Hz]          ← ear/listen.py
    ↓ scipy resample_poly up=160 down=441
[16000Hz]
    ↓ faster-whisper small int8 cpu          ~4.6s
[texto]
    ↓ HTTP POST :8765/process              ~10ms overhead
[core/server.py]
    ↓ qwen2.5:7b Ollama :11434               ~3.5s
[ACTION: domain.service | entity_id: X]
    ↓ parser
[HAOS REST API :8123]
    ↓ HTTP response
[ear/listen.py]
    ↓ Piper TTS respuesta → ffplay

Latencia warm: ~8s | Latencia cold: ~15.7s
```

## Decisiones tomadas (no reabrir)

- LLM: qwen2.5:7b (phi3 descartado)
- STT: faster-whisper sobre openai-whisper
- Wake word: training propio con openWakeWord (Porcupine descartado)
- Reproducción: ffplay (aplay descartado)
- Arquitectura: todo en laptop, HAOS solo recibe REST
- Resampling: scipy.signal.resample_poly (no librosa, más rápido)
- Voz TTS: es_AR-daniela-high (claude y davefx descartadas)
- Comunicación ear↔core: HTTP REST en localhost:8765 (no IPC — permite múltiples ears)
