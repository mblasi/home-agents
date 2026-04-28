# Master Plan - Red de Agentes Locales
# Matías Blasi | matias@blasi.ar
# Última actualización: 2026-04-27

---

## CONTEXTO DEL SISTEMA

### Hardware
```
Laptop:     AMD Ryzen 9 5900HX (Zen 3, 8 cores / 16 threads, hasta 4.6GHz)
GPU:        Radeon Vega 8 integrada (comparte RAM, no útil para ML)
RAM:        64GB DDR4
Storage:    (pendiente documentar)
Red:        LAN local con HAOS
```

### Software base
```
OS:         Gentoo Linux
Kernel:     x86_64
Shell:      zsh
Python:     3.13.12
Node:       v18.14.1 (presente en sistema)
Compiler:   GCC 15.2.1 (znver3 optimizado)
Audio:      ALSA puro (sin PulseAudio ni PipeWire)
Micrófono:  ALC256 Analog (hw:1,0) - soporta 44100Hz y 48000Hz
```

### Python Environment
```
Ubicación:  ~/ai-env (venv, activar con: source ~/ai-env/bin/activate)
Gestor:     pip 26.0.1 + uv 0.11.8 (instalado en root, pendiente en matias)

Paquetes instalados:
  faster-whisper      STT local
  openai-whisper      STT (backup, modelo en ~/.cache/whisper/)
  openwakeword 0.4.0  Wake word inferencia
  pyaudio 0.2.14      Captura de audio
  sounddevice         Audio alternativo
  soundfile           Lectura/escritura de audio
  numpy 2.4.4         Cómputo numérico
  scipy 1.17.1        Procesamiento de señales (resampleo)
  torch               PyTorch CPU only
  torchaudio          Audio con PyTorch
  torchinfo           Info de modelos
  torchmetrics        Métricas de training
  pytorch-lightning   Training framework
  audiomentations     Augmentación de audio
  torch-audiomentations  Augmentación GPU/CPU
  speechbrain         Procesamiento de voz
  onnxruntime 1.24.4  Inferencia ONNX
  scikit-learn 1.8.0  ML clásico
  huggingface_hub     Descarga de modelos HF
  requests            HTTP client
  fastapi             API server
  uvicorn             ASGI server
  pydantic            Validación de datos
  rich                Terminal UI
  tqdm                Progress bars
  pronouncing         Pronunciación (dep. openWakeWord)
  mutagen             Metadata de audio
  acoustics           Acústica (parcheado: sph_harm → sph_harm_y)
  librosa             Análisis de audio
  pandas              DataFrames
  matplotlib          Visualización
  pyyaml              YAML parser
```

### Ollama
```
Versión:    0.20.3 (compilado con vulkan + AVX2 + FMA3 + F16C)
USE flags:  vulkan, avx, avx2, f16c, fma3, sse4_2
Servicio:   systemd/openrc en localhost:11434

Modelos instalados:
  qwen2.5:7b      MODELO PRINCIPAL - 3.5s latencia, formato correcto
  phi3-ha:latest  Customizado para HA (más lento, entity_ids inventados)
  phi3:mini       Descartado (24.8s, formato incorrecto)
  llama3:8b       Disponible, no testeado para domótica
```

### Piper TTS
```
Binario:    ~/.local/bin/piper/piper (v1.2.0)
Voces:      ~/.local/share/piper/

Voces instaladas:
  es_AR-daniela-high.onnx    Femenina argentina  ← usada para training
  es_MX-claude-high.onnx     Masculina mexicana  ← candidata TTS respuesta
  es_ES-davefx-medium.onnx   Masculina española  ← candidata TTS respuesta
  es_ES-sharvard-medium.onnx Femenina española   ← para diversidad training

Reproducción: ffplay -autoexit -nodisp archivo.wav
              (aplay NO funciona sin parámetros explícitos)
```

### faster-whisper
```
Modelo:     small (descargado desde HuggingFace, en cache de HF)
Device:     CPU
Compute:    int8
Idioma:     es (español, 100% confianza en tests)
Latencia:   ~4.6s para 5s de audio
```

### Audio Pipeline
```
Problema:   ALC256 no soporta 16000Hz (necesario para STT/WakeWord)
Solución:   Grabar a 44100Hz → resamplear con scipy.signal.resample_poly
Ratio:      up=160, down=441 (44100 → 16000)
Device idx: 4 (HD-Audio Generic: ALC256 Analog hw:1,0)
```

### Home Assistant OS (HAOS)
```
Hardware:   PC vieja dedicada en la red local
Acceso:     http://[IP-HAOS]:8123
Token:      pendiente documentar (Long-Lived Access Token)
Entity IDs: pendiente mapear los reales
Estrategia: HAOS solo recibe órdenes via REST API
            Todo el procesamiento (STT/LLM/TTS) corre en laptop
```

### openWakeWord Training
```
Repo:       ~/ai-lab/wakeword/openWakeWord/
Scripts:    ~/ai-lab/wakeword/generate_samples.py
            ~/ai-lab/wakeword/generate_samples_multi.py
Data:       ~/ai-lab/wakeword/data/capitán/positive/  (90 samples, 1 voz)
            ~/ai-lab/wakeword/data/capitán/negative/  (pendiente)
Parche:     acoustics/directivity.py: sph_harm → sph_harm_y (scipy compat)
```

### Estructura de directorios
```
~/ai-lab/
├── masterplan/
│   └── estado.md           ← este archivo
├── wakeword/
│   ├── openWakeWord/       ← repo clonado
│   ├── data/
│   │   └── capitán/
│   │       ├── positive/   ← 90 samples WAV generados
│   │       └── negative/   ← pendiente
│   ├── generate_samples.py
│   └── generate_samples_multi.py
├── models/                 ← modelos GGUF (pendiente poblar)
├── scripts/
│   └── ollama_benchmark.py
├── ha-bridge/              ← código del servidor principal
└── logs/

~/.cache/
└── whisper/                ← modelos de faster-whisper (HuggingFace cache)

~/.local/
├── bin/piper/piper
└── share/piper/            ← modelos de voz .onnx
```

---

## MASTERPLAN

### FASE 1 - Fundación del Agente de Domótica
```
Objetivo: Agente de voz funcionando end-to-end con HAOS
Estado:   EN CURSO (~70% completo)
```

#### Completado
- [x] 1.1  Stack base instalado (Ollama, Whisper, Piper, PyAudio)
- [x] 1.2  Audio pipeline: captura 44100Hz → resampleo 16000Hz
- [x] 1.3  STT validado: faster-whisper español, 100% confianza
- [x] 1.4  LLM validado: qwen2.5:7b, 3.5s, formato ACTION correcto
- [x] 1.5  Pipeline completo voz→STT→LLM validado (15.7s total)
- [x] 1.6  openWakeWord: repo clonado, dependencias OK, train.py importa
- [x] 1.7  Piper: 4 voces españolas descargadas
- [x] 1.8  Samples positivos "Capitán" generados (90 samples, voz daniela)

#### Pendiente
- [x] 1.9  Elegir voz TTS para respuestas → es_AR-daniela-high.onnx
- [x] 1.10 Regenerar samples con 4 voces → 360 samples (daniela, claude, davefx, sharvard)
- [x] 1.11 Generar samples negativos con Piper → 1320 samples (45 frases × 6 vel × 4 voces, incl. hard negatives)
- [x] 1.12 Extracción de features con embedding_model.onnx → pos=(360,16,96), neg=(1320,16,96)
- [x] 1.13 Training del clasificador → 10k steps, DNN 128-dim, ~20s en CPU
- [x] 1.14 Exportar modelo a ONNX → ~/.local/share/wakeword/capitan.onnx (848KB)
- [ ] 1.15 Integrar wake word al pipeline completo
- [ ] 1.16 Conectar con HAOS real (token + entity_ids reales)
- [ ] 1.17 Parser de acciones robusto + ejecución via REST API
- [ ] 1.18 Feedback por voz (Piper responde confirmación)
- [ ] 1.19 Test end-to-end: "Capitán" → acción ejecutada en HAOS

#### Decisiones pendientes
- [x] Voz TTS respuesta: es_AR-daniela-high.onnx (única voz argentina disponible en Piper)
- [ ] Latencia aceptable: 15.7s actual, ¿optimizar o avanzar?

---

### FASE 2 - Agente Domótica Completo
```
Objetivo: Sistema robusto, contextual y con memoria del hogar
Estado:   Pendiente (inicia cuando FASE 1 esté completa)
```
- [ ] 2.1  RAG con estado dinámico de HAOS (FAISS + embeddings)
- [ ] 2.2  Context window inteligente (solo entidades relevantes)
- [ ] 2.3  Parser de acciones v2 (manejo de errores, validación)
- [ ] 2.4  Manejo de ambigüedad ("las luces" → ¿cuáles?)
- [ ] 2.5  Historial de conversación en sesión
- [ ] 2.6  Automatizaciones por voz ("cuando llegue a casa, encendé todo")
- [ ] 2.7  Satellite en habitaciones (RPi Zero 2W o ESP32 con micrófono)
- [ ] 2.8  Fine-tuning con entity_ids y patrones reales de tu casa
- [ ] 2.9  Wake word multi-persona (detectar voz de distintos miembros)

---

### FASE 3 - Infraestructura Multi-Agente
```
Objetivo: Orquestador que coordina todos los agentes
Estado:   Pendiente
```
- [ ] 3.1  Diseño del protocolo de comunicación entre agentes
- [ ] 3.2  Orquestador central (FastAPI, enruta por intención)
- [ ] 3.3  Router de intención (qué agente responde a qué)
- [ ] 3.4  Memoria compartida (contexto cross-agente)
- [ ] 3.5  Sistema de logging y observabilidad
- [ ] 3.6  API unificada para todos los agentes
- [ ] 3.7  Dashboard de estado de la red de agentes

---

### FASE 3.5 - Integración WhatsApp
```
Objetivo: Canal de texto y audio hacia el orquestador vía WhatsApp
Estado:   Pendiente (inicia cuando FASE 3 tenga orquestador básico)
Deps:     FASE 3.2 (orquestador), FASE 1.3 (STT), FASE 1 TTS
Privacidad: solo números autorizados, todo corre local
```

#### Etapa A - Canal de texto
- [ ] 3.5.1  Elegir cliente WA: whatsapp-web.js (Node 18) vs evolution-api (self-hosted REST)
- [ ] 3.5.2  Setup del cliente: sesión persistente con QR scan, reconexión automática
- [ ] 3.5.3  Webhook receiver en el orquestador (FastAPI endpoint /wa/inbound)
- [ ] 3.5.4  Whitelist de números autorizados (solo responde a contactos configurados)
- [ ] 3.5.5  Routing texto → orquestador → agente → respuesta de vuelta por WA
- [ ] 3.5.6  Manejo de contexto por número: historial de conversación en sesión

#### Etapa B - Canal de audio (PTT)
- [ ] 3.5.7  Recibir mensajes de voz (PTT) de WhatsApp → descargar OGG/Opus
- [ ] 3.5.8  Convertir OGG → WAV 16000Hz (ffmpeg o librosa)
- [ ] 3.5.9  Pasar por faster-whisper → texto → orquestador (mismo pipeline que mic)
- [ ] 3.5.10 Respuesta: opción texto o audio generado con Piper → enviar nota de voz

#### Decisiones pendientes
- [ ] Cliente WA: whatsapp-web.js (más simple, Node) vs evolution-api (REST genérico, más robusto)
- [ ] Respuesta: ¿siempre texto o detectar si el usuario mandó audio → responder audio?
- [ ] Persistencia de sesión WA: ¿LocalAuth en disco o base de datos?

---

### FASE 4 - Agente Clima
```
Objetivo: Consultas de clima por voz + integración con domótica
Estado:   Pendiente
```
- [ ] 4.1  Integración Open-Meteo API (libre, sin key, precisa)
- [ ] 4.2  Datos históricos y pronóstico extendido local
- [ ] 4.3  Integración con domótica:
           lluvia → cerrar persianas
           frío extremo → ajustar calefacción
           viento fuerte → alertas
- [ ] 4.4  Alertas proactivas por voz
- [ ] 4.5  Contexto geográfico (tu ubicación, sin enviarla a terceros)

---

### FASE 5 - Agente Agenda
```
Objetivo: Gestión de agenda por voz, privada y local
Estado:   Pendiente
```
- [ ] 5.1  CalDAV local (Radicale en HAOS o servidor dedicado)
- [ ] 5.2  Sincronización opcional con Google Calendar
- [ ] 5.3  Consultas por voz:
           "¿qué tengo mañana?"
           "agendá reunión el viernes a las 10"
           "¿cuándo es el próximo feriado?"
- [ ] 5.4  Integración con domótica:
           alarma de agenda → encender luces gradualmente
           reunión en 15min → recordatorio por voz
- [ ] 5.5  Recordatorios proactivos sin trigger de voz
- [ ] 5.6  Vista de agenda en panel de HAOS

---

### FASE 6 - Agente Inversiones
```
Objetivo: Consultas financieras por voz, datos privados locales
Estado:   Pendiente
Nota:     Datos sensibles, nunca salen de la red local
```
- [ ] 6.1  Definir fuentes de datos:
           Yahoo Finance (acciones internacionales)
           BCRA API (dólar, tasas Argentina)
           Ambito/Infobae scraping (mercado local)
- [ ] 6.2  Scraper/poller de cotizaciones (actualización periódica)
- [ ] 6.3  Portfolio local (tus activos, cifras, completamente privado)
- [ ] 6.4  Consultas por voz:
           "¿cómo está el dólar?"
           "¿cómo va mi portfolio hoy?"
           "¿cuánto subió GGAL esta semana?"
- [ ] 6.5  Alertas configurables (precio objetivo, variación %)
- [ ] 6.6  RAG sobre noticias financieras (scraping + embeddings)
- [ ] 6.7  Resumen diario automático al llegar a casa

---

### FASE 7 - Agente Viajes
```
Objetivo: Asistente de planificación y consulta de viajes
Estado:   Pendiente
```
- [ ] 7.1  Definir casos de uso concretos con tu familia
- [ ] 7.2  RAG sobre documentos de viaje (pasaportes, reservas, PDFs)
- [ ] 7.3  Integración con APIs de clima en destinos
- [ ] 7.4  Consultas por voz:
           "¿qué clima hace en Roma en octubre?"
           "¿tengo el pasaporte vigente?"
           "¿cuándo es el próximo viaje?"
- [ ] 7.5  Planificación con LLM (itinerarios, sugerencias)
- [ ] 7.6  Alertas de documentos por vencer

---

### FASE 8 - Migración a Servidor Dedicado
```
Objetivo: Mover toda la inferencia a hardware dedicado y escalar a modelos más potentes
Estado:   Pendiente (planificar en paralelo con FASE 3-4, ejecutar cuando el sistema esté estable)
Laptop:   Pasa a rol de cliente/satélite y entorno de desarrollo
```

#### Etapa A - Definición de hardware objetivo
- [ ] 8.1  Definir presupuesto y timeline de compra
- [ ] 8.2  CPU objetivo: AMD Ryzen 9 7900X / 7950X o Intel i9-13900K
           (muchos cores para inferencia paralela multi-agente)
- [ ] 8.3  RAM objetivo: 128GB DDR5 mínimo (correr 2-3 modelos grandes simultáneos)
- [ ] 8.4  GPU objetivo para inferencia:
           RTX 4070 Ti 12GB  → buena relación precio/VRAM
           RTX 3090 24GB     → VRAM ideal para modelos 20B+
           RTX 4090 24GB     → techo actual para un solo agente grande
- [ ] 8.5  GPU objetivo para fine-tuning (puede ser la misma o segunda):
           RTX 3060 12GB     → mínimo para LoRA
           RTX 3090 24GB     → cómodo para modelos hasta 13B
- [ ] 8.6  Storage: SSD NVMe ~2TB para modelos + HDD para datos y backups
- [ ] 8.7  Red: ethernet gigabit al switch (no WiFi para el servidor)

#### Etapa B - Setup del servidor
- [ ] 8.8  OS: Debian stable o Ubuntu Server LTS (priorizar estabilidad sobre cutting-edge)
- [ ] 8.9  Drivers CUDA + cuDNN para GPU NVIDIA
- [ ] 8.10 Ollama con soporte GPU (inferencia ~10-30x más rápida que CPU)
- [ ] 8.11 Recompilar faster-whisper con soporte CUDA
- [ ] 8.12 Docker Compose para todos los servicios (orquestador, agentes, bases de datos)
- [ ] 8.13 IP estática en LAN, hostname fijo (ej: `agentes.local`)
- [ ] 8.14 Acceso SSH seguro desde laptop y otros dispositivos de la red

#### Etapa C - Migración de servicios
- [ ] 8.15 Migrar Ollama + modelos al servidor (servidor nuevo como :11434)
- [ ] 8.16 Migrar orquestador FastAPI (FASE 3) al servidor
- [ ] 8.17 Migrar todos los agentes al servidor
- [ ] 8.18 Laptop queda como: cliente de voz (mic/speaker) + entorno de desarrollo
- [ ] 8.19 Período de operación paralela: laptop + servidor corriendo juntos para validar
- [ ] 8.20 Cutover: redirigir laptop al servidor, apagar servicios locales

#### Etapa D - Escalado de modelos
- [ ] 8.21 Modelos de inferencia con GPU:
           qwen2.5:14b   → mejor razonamiento, cabe en 12GB VRAM
           qwen2.5:32b   → contexto largo, requiere 24GB VRAM o CPU offload
           qwen2.5:72b   → máxima capacidad, requiere multi-GPU o CPU offload con 128GB RAM
- [ ] 8.22 Whisper large-v3 en GPU (~0.5s latencia vs 4.6s actual en CPU)
- [ ] 8.23 Modelos especializados por agente (ej: modelo financiero para agente inversiones)
- [ ] 8.24 Fine-tuning con LoRA para dominio hogar (entity_ids reales, patrones propios)

#### Etapa E - Operaciones y confiabilidad
- [ ] 8.25 UPS para el servidor (evitar cortes abruptos con modelos en memoria)
- [ ] 8.26 Systemd units para auto-restart de todos los servicios
- [ ] 8.27 Monitoreo de recursos: temperatura GPU/CPU, uso de VRAM, latencias por agente
- [ ] 8.28 Alertas si un servicio cae (notificación por WhatsApp vía FASE 3.5)
- [ ] 8.29 Backup automático de modelos fine-tuneados y configuraciones
- [ ] 8.30 Wake-on-LAN desde laptop (servidor puede estar en suspend fuera de horario)

#### Latencias objetivo post-migración (con GPU)
```
STT (Whisper large-v3 GPU):   ~0.3-0.5s   (vs 4.6s actual)
LLM qwen2.5:14b GPU:          ~1-2s        (vs 3.5s actual con 7b CPU)
TTS Piper (sin cambio):       ~0.5s
Total estimado:               ~2-3s        (vs 8s actual warm)
```

---

## PIPELINE ACTUAL (para referencia rápida)

```
[MIC hw:1,0 44100Hz]
        ↓
[resampleo scipy: up=160, down=441 → 16000Hz]
        ↓
[faster-whisper small, int8, CPU]  ~4.6s
        ↓
[qwen2.5:7b via Ollama :11434]     ~3.5s
        ↓
[parser ACTION: domain.service | entity_id: X]
        ↓
[HAOS REST API :8123]
        ↓
[Piper TTS respuesta]
```

## LATENCIAS ACTUALES
```
STT (5s audio):     4.6s
LLM (warm):         3.5s
LLM (cold start):  11.2s
Total (warm):       ~8s
Total (cold):      ~15.7s
```

## COMANDOS DE USO FRECUENTE
```zsh
# Activar entorno
source ~/ai-env/bin/activate

# Iniciar Ollama (si no está corriendo)
ollama serve &

# Ver modelos disponibles
ollama list

# Test rápido del pipeline STT
python ~/ai-lab/scripts/test_stt.py

# Monitor de recursos
python ~/ai-lab/scripts/monitor.py

# Generar samples de wake word
python ~/ai-lab/wakeword/generate_samples_multi.py

# Training wake word (cuando estén los negativos)
cd ~/ai-lab/wakeword/openWakeWord
python -m openwakeword.train --config ~/ai-lab/wakeword/config.yaml
```

---

## CÓMO RETOMAR ESTE PLAN

Al inicio de cada sesión escribir:
> "retomamos el master plan"

El asistente responderá con:
- Fase y paso actual
- Qué se completó en la sesión anterior  
- Próximo paso concreto
- Decisiones pendientes si las hay

---

## NOTAS Y DECISIONES TOMADAS

### 2026-04-27
- Elegido qwen2.5:7b como LLM principal (phi3:mini descartado por lento)
- phi3-ha descartado (inventa entity_ids)
- Opción 3 elegida para wake word (training propio con openWakeWord)
- Porcupine descartado (dependencia externa, límites de uso)
- faster-whisper elegido sobre openai-whisper (HuggingFace download, más rápido)
- aplay descartado para TTS, usar ffplay
- Arquitectura decidida: todo el procesamiento en laptop, HAOS solo recibe REST calls
- acoustics parcheado para compatibilidad con scipy 1.17.1 / Python 3.13

### Pendiente decidir
- Voz TTS para respuestas: es_MX-claude-high vs es_ES-davefx-medium
- Latencia: ¿optimizar ahora o avanzar con la integración?
- Hardware servidor: timing y presupuesto
```

---

```zsh
# Guardar el archivo
mkdir -p ~/ai-lab/masterplan
# Copiar el contenido de arriba a:
# ~/ai-lab/masterplan/estado.md

# Verificar
wc -l ~/ai-lab/masterplan/estado.md
echo "Master plan guardado"
```

Cuando quieras retomar escribís **"retomamos el master plan"** y arrancamos desde el paso 1.9.
