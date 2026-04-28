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
  es_AR-daniela-high.onnx    ← usada para training de wake word
  es_MX-claude-high.onnx     ← candidata para respuestas
  es_ES-davefx-medium.onnx   ← candidata para respuestas
  es_ES-sharvard-medium.onnx ← diversidad en training
```

### openWakeWord
```
Repo:   ~/ai-lab/wakeword/openWakeWord/
Data:   ~/ai-lab/wakeword/data/capitán/positive/  (90 samples WAV, voz daniela)
        ~/ai-lab/wakeword/data/capitán/negative/  (pendiente)
Wake word objetivo: "Capitán"
```

Parche aplicado (no revertir):
`acoustics/directivity.py` — `sph_harm` → `sph_harm_y` (scipy 1.17.1 / Python 3.13)

## Home Assistant OS (HAOS)

```
Acceso:    http://[IP-HAOS]:8123
Estrategia: HAOS solo recibe órdenes via REST API
            Todo el procesamiento (STT/LLM/TTS) corre en la laptop
Token:     pendiente documentar (Long-Lived Access Token)
Entity IDs: pendiente mapear
```

## Estructura del repo

```
masterplan/
  estado.md        plan completo con estado, latencias y decisiones
  issues.yaml      mapeo task_id → GitHub issue number

wakeword/
  openWakeWord/    repo clonado
  data/capitán/    samples de training
  generate_samples.py
  generate_samples_multi.py

scripts/
  sync_issues.py          sincroniza estado.md con GitHub issues
  test_audio_pipeline.py  prueba cada componente de audio

ha-bridge/         código del servidor principal (pendiente)
models/            modelos GGUF (pendiente poblar)
logs/

interagent/        concepto del producto Interagent (red de redes de agentes)
  CONCEPT.md
  protocol/
  sdk/
  monetization/
```

## Comandos frecuentes

```zsh
# Activar entorno
source ~/ai-env/bin/activate

# Ollama
ollama serve &
ollama list

# Test audio pipeline
python scripts/test_audio_pipeline.py

# Generar samples wake word
python wakeword/generate_samples_multi.py

# Training wake word (cuando haya negativos)
cd wakeword/openWakeWord
python -m openwakeword.train --config ~/ai-lab/wakeword/config.yaml

# Sync issues con GitHub
python scripts/sync_issues.py
```

## Pipeline actual

```
[MIC hw:1,0 44100Hz]
    ↓ scipy resample_poly up=160 down=441
[16000Hz]
    ↓ faster-whisper small int8 cpu          ~4.6s
[texto]
    ↓ qwen2.5:7b Ollama :11434               ~3.5s
[ACTION: domain.service | entity_id: X]
    ↓ parser
[HAOS REST API :8123]
    ↓
[Piper TTS respuesta → ffplay]

Latencia warm: ~8s | Latencia cold: ~15.7s
```

## Decisiones tomadas (no reabrir)

- LLM: qwen2.5:7b (phi3 descartado)
- STT: faster-whisper sobre openai-whisper
- Wake word: training propio con openWakeWord (Porcupine descartado)
- Reproducción: ffplay (aplay descartado)
- Arquitectura: todo en laptop, HAOS solo recibe REST
- Resampling: scipy.signal.resample_poly (no librosa, más rápido)
