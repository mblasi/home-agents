# Master Plan - Red de Agentes Locales
# Matías Blasi | matias@blasi.ar
# Última actualización: 2026-04-30

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
Ubicación:  ~/home-agents-env (venv, activar con: source ~/home-agents-env/bin/activate)
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
Acceso:     http://192.168.68.101:8123
Token:      en .env (Long-Lived Access Token, excluido del repo)
Estrategia: HAOS solo recibe órdenes via REST API
            Todo el procesamiento (STT/LLM/TTS) corre en laptop

Entity IDs relevantes:
  light.wiz_rgbw_tunable_1fdbc2          → luz principal (WiZ RGBW)
  climate.midea_ac_150633093419021        → aire acondicionado (Midea)
  cover.tze200_nhyj64w2_ts0601           → persiana / toldo
  switch.garaje_light                    → luz del garaje
  switch.patio_light                     → luz del patio
  switch.puerta_principal_light          → luz de la puerta principal
  switch.mi_smart_kettle_pro             → pava / hervidor
  switch.mi_smart_air_fryer_3_5l         → freidora
  switch.agua_principal_valvula_de_cierre → válvula agua principal
  switch.zone_1 … switch.zone_8          → zonas de riego (Rachio)
  media_player.samsung_q8_65_tv          → TV principal (65")
  media_player.samsung_7_series_50       → TV del cuarto (50")
  media_player.echo_de_matias            → Echo de Matías
```

### openWakeWord Training
```
Repo:       ~/workspace/home-agents/ear/wakeword/openWakeWord/
Scripts:    ~/workspace/home-agents/ear/wakeword/generate_samples.py
            ~/workspace/home-agents/ear/wakeword/generate_samples_multi.py
Data:       ~/workspace/home-agents/ear/wakeword/data/capitán/positive/  (90 samples, 1 voz)
            ~/workspace/home-agents/ear/wakeword/data/capitán/negative/  (pendiente)
Parche:     acoustics/directivity.py: sph_harm → sph_harm_y (scipy compat)
```

### Estructura de directorios
```
~/workspace/home-agents/                         ← home-agents (repo umbrella)
├── ear/                          ← submodule: home-agents-ear
│   ├── listen.py                 wake word → STT → HTTP/core → TTS
│   ├── tts.py                    Piper TTS → ffplay
│   ├── panel_*.py                paneles Rich para zellij dashboard
│   ├── dashboard.sh/kdl          lanzador del dashboard
│   ├── run.sh / capitan.service  systemd service
│   └── wakeword/
│       ├── openWakeWord/         submodule del repo externo
│       ├── data/capitán/positive/ (90 samples WAV)
│       └── data/capitán/negative/
├── core/                         ← submodule: home-agents-core
│   ├── server.py                 FastAPI en :8765
│   ├── agent.py                  texto → LLM → ACTION → HAOS
│   ├── agent_registry.py         dispatcher + registry de agentes
│   ├── ha_client.py              cliente REST HAOS + mapa de entidades
│   └── capitan-core.service      systemd service
├── masterplan/
│   └── estado.md                 ← este archivo
├── scripts/
│   └── sync_issues.py
└── interagent/                   concepto del producto (no ejecutable)

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
Estado:   COMPLETA
```
- [x] 1.1  Stack base instalado (Ollama, Whisper, Piper, PyAudio)
- [x] 1.2  Audio pipeline: captura 44100Hz → resampleo 16000Hz
- [x] 1.3  STT validado: faster-whisper español, 100% confianza
- [x] 1.4  LLM validado: qwen2.5:7b, 3.5s, formato ACTION correcto
- [x] 1.5  Pipeline completo voz→STT→LLM validado (15.7s total)
- [x] 1.6  openWakeWord: repo clonado, dependencias OK, train.py importa
- [x] 1.7  Piper: 4 voces españolas descargadas
- [x] 1.8  Samples positivos "Capitán" generados (90 samples, voz daniela)
- [x] 1.9  Elegir voz TTS para respuestas → es_AR-daniela-high.onnx
- [x] 1.10 Regenerar samples con 4 voces → 360 samples (daniela, claude, davefx, sharvard)
- [x] 1.11 Generar samples negativos con Piper → 1320 samples (45 frases × 6 vel × 4 voces, incl. hard negatives)
- [x] 1.12 Extracción de features con embedding_model.onnx → pos=(360,16,96), neg=(1320,16,96)
- [x] 1.13 Training del clasificador → 10k steps, DNN 128-dim, ~20s en CPU
- [x] 1.14 Exportar modelo a ONNX → ~/.local/share/wakeword/capitan.onnx (848KB)
- [x] 1.15 Integrar wake word al pipeline completo → listen.py, score=0.96, STT funcional
- [x] 1.16 Conectar con HAOS real → ha_client.py, IP documentada, 13 entity_ids mapeados
- [x] 1.17 Parser de acciones robusto + ejecución via REST API → agent.py, qwen2.5:7b, 5/5 comandos correctos
- [x] 1.18 Feedback por voz → tts.py, voz daniela, integrado en listen.py
- [x] 1.19 Test end-to-end: "Capitán" → acción ejecutada en HAOS → confirmación por voz ✓
- [x] 1.20 Servicio systemd para el agente → capitan.service (user), start/stop manual con systemctl --user
- [x] 1.21 Dashboard zellij para el agente → dashboard.sh, 4 paneles: score animado, historial, latencias, logs
- [x] 1.22 Modularización en submodules → ear (audio/UI) + core (FastAPI :8765, LLM, HAOS); comunicación via HTTP POST /process

#### Decisiones
- [x] Voz TTS respuesta: es_AR-daniela-high.onnx (única voz argentina disponible en Piper)
- [x] Latencia aceptable: 15.7s actual → avanzar con FASE 2, optimizar en FASE 8 con hardware dedicado

---

### FASE 2 - Agente Domótica Completo
```
Objetivo: Sistema robusto, contextual y con memoria del hogar
Estado:   COMPLETA
```
- [x] 2.1  RAG con estado dinámico de HAOS (FAISS + embeddings)
- [x] 2.2  Context window inteligente (solo entidades relevantes)
- [x] 2.3  Parser de acciones v2 (manejo de errores, validación)
- [x] 2.4  Manejo de ambigüedad ("las luces" → ¿cuáles?)
- [x] 2.10 Gestión de conversaciones: identidad, contexto multi-turno y ciclo de vida

#### Postergadas (movidas a otras fases)
- ~~2.5  Historial de conversación en sesión~~ → implementado como parte de 2.10
- ~~2.6  Automatizaciones por voz~~ → FASE 9.10 (requests condicionales en el coordinador LLM)
- ~~2.7  Satellite en habitaciones~~ → Anexo A.2 (red de nodos de audio multi-ambiente)
- ~~2.8  Fine-tuning con entity_ids~~ → FASE 8.24 (fine-tuning con LoRA en servidor con GPU)
- ~~2.9  Wake word multi-persona~~ → FASE 2.5 tasks 2.5.6 + 2.5.7 (enrollment + speaker ID).
         Prerequisito de FASE 11.7 (amigo/asesor personalizado por usuario).

#### Estado
```
FASE 2 COMPLETA
```

---

### FASE 2.5 - Gestión de Usuarios
```
Objetivo: Sistema de identidad que permite reconocer quién habla, definir su rol y
          parentesco, y personalizar la experiencia.
Estado:   COMPLETA (2.5.10 incluida — ProfileAgent)
Stack:    resemblyzer (GE2E 256-dim), JSON + .npy local, RBAC por rol
```
- [x] 2.5.1  Modelo de usuario: roles (admin/familiar/niño/invitado), relaciones de parentesco,
             preferencias y agentes propios por usuario — users.py
- [x] 2.5.2  Persistencia: ~/.local/share/capitan/users.json + embeddings/*.npy (biométrico, local)
- [x] 2.5.3  API REST en core: GET/POST/PATCH/DELETE /users + POST /users/reload
- [x] 2.5.4  Bootstrap admin: al arrancar sin usuarios, listen.py avisa por voz para registrarse
- [x] 2.5.5  Comando de voz "Capitán, registrarme" — enrollment guiado iniciado desde listen.py
- [x] 2.5.6  Enrollment por voz: 5 frases predefinidas, tono inicio/fin, media L2-normalizada
             guardada como perfil — enrollment.py
- [x] 2.5.7  Identificación en tiempo real: resemblyzer embed + cosine similarity en el audio
             post-wake-word, speaker_id + confidence en source del POST /process — speaker_id.py
- [x] 2.5.8  RBAC: tabla de permisos por rol en rbac.py, allowed() + deny_message(),
             aplicado en /process antes de delegar al agente
- [x] 2.5.9  Panel de usuarios: panel_users.py con Rich, lista de usuarios + speaker activo
             con confidence, lee /tmp/capitan/speaker.json y GET /users
- [x] 2.5.10 Gestión de información personal por voz: comandos para actualizar campos del
             propio perfil sin tocar el backoffice.
             Ej: "mi pasaporte vence el 15 de marzo de 2027", "mi nombre es Matías",
             "tengo 38 años", "prefiero respuestas cortas".
             El agente extrae el campo y el valor, valida, y hace PATCH /users/{id}.
             Prerequisito natural: cualquier agente que necesite datos personales del usuario
             (fase 7 usa documentos de viaje, fase 11 usa preferencias del usuario).

---

### FASE 2.6 - Onboarding de Usuario y Wake Word Personalizado
```
Objetivo: Unificar la creación de usuario y el perfeccionamiento del reconocimiento en
          un único flujo coherente accesible por dos canales: comando de voz y dashboard web.
          En ambos casos el flujo cubre: datos básicos → speaker ID (resemblyzer) → muestras
          de wake word. Resuelve falsos positivos y baja detección reemplazando el modelo
          TTS-only por uno entrenado con muestras reales de cada usuario.
          Métricas de precisión visibles en el perfil + sugerencias de mejora continua.
Estado:   COMPLETA
Deps:     FASE 2.5 (users.py, enrollment.py, speaker_id.py), FASE 12.13 (sección Usuarios)
Stack:    openwakeword (ya existe), resemblyzer (ya existe), SSE backoffice, HTMX wizard
```

#### Fix inmediato (sin reentrenamiento)
- [x] 2.6.1  Gate post-wake-word: si speaker_id == "unknown" y confidence < umbral
             configurable (`WAKEWORD_REQUIRE_KNOWN_SPEAKER=true` en .env), descarta el comando
             y emite tono "no reconocido". Usa resemblyzer existente de 2.5.7.
             Reduce falsos positivos de terceros al instante, sin tocar el modelo ONNX.

#### Flujo de onboarding unificado
- [x] 2.6.2  `core/onboarding.py` — máquina de estados del flujo de onboarding: pasos
             (datos_basicos → frases_speaker_id → muestras_wake_word → completo).
             Estado persistido en users.json por usuario (onboarding_step, onboarding_complete).
             Mismo flujo consumido por voz y por web.
- [x] 2.6.3  Onboarding por voz: comando "Capitán, agregar usuario" inicia el flujo guiado
             desde `ear/listen.py`. TTS pregunta nombre, rol y relación de parentesco;
             usuario responde por voz. Luego guía las frases de speaker ID (ya existentes en
             enrollment.py de 2.5.6) y las muestras de wake word (2.6.5). Al completar,
             POST /users crea el usuario y POST /users/{id}/wakeword/enroll cierra el flujo.
- [x] 2.6.4  Onboarding por web: wizard multi-paso en backoffice `/users/new`:
             Paso 1: nombre, rol, parentesco (form HTMX).
             Paso 2: frases de speaker ID — botón "Iniciar grabación" activa el mic del
             dispositivo ear vía SSE, progress bar en tiempo real.
             Paso 3: muestras de wake word — igual que paso 2 pero con instrucciones "di Capitán".
             Admin puede lanzar el flujo para cualquier usuario desde la lista de usuarios.

#### Almacenamiento y reentrenamiento
- [x] 2.6.5  `core/wakeword_samples.py` — almacena WAVs de muestras reales por usuario en
             `~/.local/share/capitan/wakeword_samples/{user_id}/` (máx 200 samples),
             metadata en JSON: fecha, duración, aceptado/rechazado, canal (voz/web).
             Endpoint `POST /users/{id}/wakeword/enroll` acepta inicio del flujo guiado;
             SSE stream de progreso para el cliente (sample N/30 ok/rechazado).
- [x] 2.6.6  `POST /wakeword/train` (global) — retrain con muestras reales de todos los
             usuarios enrolled + TTS base; exporta nuevo ONNX a ~/.local/share/wakeword/;
             recarga modelo en listen.py sin reiniciar. BackgroundTask en core/server.py.

#### Métricas y sugerencias
- [x] 2.6.7  Métricas de precisión en operación — `listen.py` registra por usuario:
             detecciones (TP), falsos positivos (wake word + speaker desconocido), rechazos RBAC.
             Persiste en `~/.local/share/capitan/wakeword_metrics.json`.
             API: `GET /users/{id}/wakeword/metrics`.
- [x] 2.6.8  Backoffice perfil de usuario — sección "Reconocimiento de voz":
             estado del onboarding (completo / incompleto / en progreso), precisión (TP/(TP+FP)),
             samples grabados, fecha último enrollment y último reentrenamiento.
             Sugerencias automáticas renderizadas como alertas:
             "menos de 20 muestras — completá el enrollment",
             "FP > 15% — grabá muestras en condiciones de ruido",
             "modelo no incluye tu voz — entrená el modelo",
             "muestras de hace más de 90 días — considera re-enrollarte".

---

### FASE 2.7 - Agentes de Administración
```
Objetivo: Agentes de voz exclusivos para el rol admin que exponen por voz las mismas
          capacidades que el backoffice web: gestión de usuarios y gestión del sistema.
          Siguen el mismo patrón que ProfileAgent: LLM extrae acción estructurada → se aplica.
Estado:   COMPLETA
Deps:     FASE 2.5 (users.py, RBAC), FASE 3 (orquestador, RBAC en /process)
RBAC:     Solo el rol admin tiene acceso (* en PERMISSIONS). El resto recibe deny_message.
```
- [x] 2.7.1  UserMgmtAgent (user_mgmt_agent.py): gestión de usuarios por voz.
             Acciones: listar usuarios, ver perfil de usuario, crear usuario (name+role+relationship),
             borrar usuario, cambiar rol, otorgar/revocar acceso a agentes.
             Al crear: crea el registro y guía al nuevo usuario a decir "Capitán, registrarme"
             para completar el enrollment de speaker ID.
             availability_url → GET /users del core.
- [x] 2.7.2  SystemAgent (system_agent.py): gestión del sistema por voz.
             Acciones: estado del sistema (core/HAOS/Ollama/ear), reiniciar servicios
             (systemctl --user restart capitan-core/capitan), listar modelos Ollama,
             uso de memoria RAM, agentes activos.
             availability_url → GET /health del core.

---

### FASE 3 - Infraestructura Multi-Agente
```
Objetivo: Patrón de extensión para agentes de dominio + estado compartido cross-agente
Estado:   COMPLETA
```

- [x] 3.1  Contrato de interfaz para agentes de dominio: BaseAgent protocol en código,
           patrón de registro en agent_registry, guía para agregar FASE 4-7
- [x] 3.2  Orquestador central → server.py (FastAPI :8765, POST /process)
- [x] 3.3  Router de intención → agent_registry.dispatch() (keywords + LLM fallback)
- [x] 3.4  Estado compartido cross-agente: slot de contexto legible/escribible por cualquier
           agente activo (ej: clima sabe que llueve → haos puede ajustar persianas)
- [x] 3.5  Logging y observabilidad → /tmp/capitan/*.json + dashboard zellij
- [x] 3.6  API unificada → POST /process, GET /agents, GET /health, GET /conversations
- [x] 3.7  Dashboard de estado → panel_agents.py (agente activo, fuente, conversación)

---

### FASE 3.5 - Integración WhatsApp
```
Objetivo: Canal de texto y audio hacia el orquestador vía WhatsApp
Estado:   COMPLETA
Deps:     FASE 3.2 ✓ (orquestador implementado), FASE 1.3 ✓ (STT), FASE 1 TTS ✓
Privacidad: solo números autorizados, todo corre local
Stack:    whatsapp-web.js (Node 18), LocalAuth, POST /wa/inbound (FastAPI)
```

#### Etapa A - Canal de texto
- [x] 3.5.1  Elegir cliente WA: whatsapp-web.js (Node 18) — sesión LocalAuth en disco
- [x] 3.5.2  Setup del cliente: sesión persistente con QR scan, reconexión automática (wa/index.js)
- [x] 3.5.3  Webhook receiver en el orquestador (FastAPI endpoint POST /wa/inbound en server.py)
- [x] 3.5.4  Control de acceso por usuario: User.wa_phone resuelve número → speaker_id + RBAC por rol
- [x] 3.5.5  Routing texto → orquestador → agente → respuesta de vuelta por WA
- [x] 3.5.6  Manejo de contexto por número: source={channel:whatsapp, phone:...} → source_key único en conversations.py

#### Etapa B - Canal de audio (PTT)
- [x] 3.5.7  Recibir mensajes de voz (PTT) de WhatsApp → descargar OGG/Opus (wa/index.js handleAudio)
- [x] 3.5.8  Convertir OGG → WAV 16000Hz (ffmpeg en wa_audio.transcribe)
- [x] 3.5.9  Pasar por faster-whisper → texto → orquestador (POST /wa/inbound/audio)
- [x] 3.5.10 Respuesta: espejo de entrada — PTT → nota de voz OGG/Opus (Piper + libopus); fallback a texto

#### Decisiones tomadas
- [x] Cliente WA: whatsapp-web.js (Node 18) — más simple, sin Docker
- [x] Respuesta: espejo de entrada (texto → texto, PTT → nota de voz)
- [x] Persistencia de sesión WA: LocalAuth en ~/.local/share/capitan/wa-session/

#### Correcciones
- [x] 3.5.11 **Fix formato @lid** — `msg.from` puede llegar como `205432...@lid` en vez de `5491...@c.us`
             (formato "linked identity" de WA moderno). Usar `msg.getContact()` para resolver el número
             real en todos los casos, en lugar de un simple `replace("@c.us", "")`.
- [x] 3.5.12 **Match por wa_lid** — `contact.number` en modo `@lid` devuelve el LID, no el teléfono.
             Solución: campo `wa_lid` en User (además de `wa_phone`). Para mensajes `@c.us` se usa
             `from_number`; para `@lid` se pasa `from_lid` al core. El core intenta match por
             `wa_phone` primero, luego por `wa_lid`. El backoffice muestra y permite editar `wa_lid`
             en el perfil de usuario.

---

### FASE 4 - Agente Clima
```
Objetivo: Consultas de clima por voz + integración con domótica
Estado:   COMPLETA
```

## Completado

- [x] 4.1  Integración Open-Meteo API (libre, sin key, precisa)
- [x] 4.2  Datos históricos y pronóstico extendido local (7 días + hourly 12h)
- [x] 4.3  Integración con domótica via shared_state:
           publica weather.is_raining, temp_outside, wind_speed, conditions
           HaosAgent puede leer estas entradas para acciones condicionales
- [x] 4.4  Alertas proactivas por voz (mecanismo genérico):
           alert_queue.py (FIFO thread-safe), server.py poller cada 15min via agent.alerts(),
           GET /alerts consume-once, ear/_alert_thread daemon (60s, solo en state=listening)
           Cualquier agente futuro puede implementar alerts() → list[str] sin registro extra
- [x] 4.5  Contexto geográfico desde .env: LATITUDE, LONGITUDE, LOCATION_NAME

---

### FASE 5 - Agente Agenda
```
Objetivo: Gestión de agenda por voz, privada y local
Estado:   COMPLETA (5.2 postergada, google-free; alarma luces → HAOS nativo)
```
- [x] 5.1  CalDAV local (Radicale en HAOS o servidor dedicado)
- [ ] 5.2  Sincronización opcional con Google Calendar
- [x] 5.3  Consultas por voz:
           "¿qué tengo mañana?"
           "agendá reunión el viernes a las 10"
           "¿cuándo es el próximo feriado?" — feriados UY via Nager.Date API
- [x] 5.4  Integración con domótica:
           alarma de agenda → encender luces gradualmente [postergado → HAOS nativo]
           reunión en 15min → recordatorio por voz ✓ (thread 1min, reminder_minutes configurable)
- [x] 5.5  Recordatorios proactivos sin trigger de voz (briefing matutino + resumen vespertino, hora configurable)
- [x] 5.6  Vista de agenda en panel de HAOS
           Radicale expuesto en LAN (0.0.0.0:5232); integración CalDAV en HA via config flow API;
           entidades: calendar.personal + calendar.feriados; tarjeta Calendar en el dashboard de HA

---

### FASE 6 - Agente Inversiones
```
Objetivo: Consultas financieras por voz, datos privados locales
Estado:   COMPLETA
Nota:     Modo dummy (recomendaciones + P&L hipotética). Portfolio por usuario (FASE 2.5).
          Fuentes: yfinance (acciones/crypto/FX) + dolarapi.com (dólar oficial/blue/MEP/CCL).
```
- [x] 6.1  Definir fuentes de datos:
           yfinance (acciones internacionales, crypto, pares FX)
           dolarapi.com (dólar oficial/blue/MEP/CCL/tarjeta)
           yfinance UYU=X (peso uruguayo)
- [x] 6.2  Cliente de cotizaciones con cache (finance_client.py):
           get_quote(), get_history(), get_price_at_date(), get_dollar_rates(), get_uyu_rate()
           Cache 10min por símbolo, 15min para dólar
- [x] 6.3  Portfolio por usuario en modo dummy (portfolio.py):
           Watchlist por usuario, registro de recomendaciones (buy/sell/hold/watch),
           P&L hipotética calculada con precio actual, persistencia ~/.local/share/capitan/
- [x] 6.4  Consultas por voz (finance_agent.py):
           "¿cómo está el dólar?" "¿cuánto vale GGAL?" "¿qué me recomendás?"
           "¿cómo fueron tus recomendaciones?" — etiqueta [REC:accion:TICKER] registra automáticamente
- [x] 6.5  Alertas configurables (finance_alerts.py):
           Brecha blue/oficial > 10%, BTC ±5%, watchlist ±5%. Umbrales via .env.
- [x] 6.6  RAG sobre noticias financieras (scraping + embeddings):
           finance_news.py — RSS Yahoo Finance por ticker, embeddings nomic-embed-text (Ollama),
           búsqueda cosine numpy, fallback keyword, índice JSON persistido, refresh async
- [x] 6.7  Resumen diario automático (en finance_alerts.check()):
           Dólar oficial/blue, UYU, movimientos de watchlist. Emite a FINANCE_BRIEFING_HOUR (8am).
- [x] 6.8  Planes de inversión diversificados (portfolio.py + finance_agent.py):
           El LLM puede emitir [PORTFOLIO:nombre|TICKER:pct,...] para crear/guardar planes
           con snapshot de precios al momento. save_plan(), list_plans(), delete_plan(),
           calculate_plan_pnl(). Soporte multi-plan por usuario, reemplazo por nombre.
           El agente inyecta los planes existentes como contexto al LLM.
- [x] 6.9  Reporte comparativo diario de planes con formato WA (finance_alerts.py):
           Al momento del briefing matutino, por cada usuario con planes guardados:
           1. Alerta TTS corta: "tu mejor plan es X con +Y%"
           2. Reporte WA rico enviado directo vía wa_notifier: tabla por plan con
              P&L por posición, ponderada total, medallas 🥇🥈🥉, mejor plan 🏆.
           Cooldown 20h por usuario. Configurable via FINANCE_BRIEFING_HOUR.
- [x] 6.10 Perfiles de riesgo por usuario + ciclo proactivo estratégico (portfolio.py + finance_agent.py):
           RISK_PROFILE_TEMPLATES (conservador/moderado/agresivo) con posiciones y umbrales de revisión.
           Tag [PROFILE:...] en system prompt: el LLM detecta el perfil en conversación y lo persiste
           via context_updates (3-tuple). _ask_llm() inyecta perfil como contexto activo.
           proactive_check() split en dos capas:
           — _strategic_checks(): hardcodeado — intent si falta perfil, plan, o P&L bajo umbral
           — proactive_check(): llama _strategic_checks() + super().proactive_check() (LLM sobre historial);
             omite LLM si no hay perfil. proactive_system_prompt específico para finanzas.
           Las alertas reactivas de precios siguen en finance_alerts.check() sin duplicación.
- [x] 6.11 Templates de planes automáticos: crear planes desde templates sin necesidad de conversación.
           Auto-crear un plan por template disponible al primer proactive_check sin planes.
           list_templates(), save_template(), delete_template() en portfolio.py — CRUD persistente
           en finance_templates.json con seed desde RISK_PROFILE_TEMPLATES. Cada template tiene
           review_threshold propio. create_plans_from_templates(user_id) crea solo los faltantes.
           _strategic_checks() reemplaza Intent 0 + Intent 1 por auto-creación silenciosa.
           CRUD en backoffice /finance/templates con formulario inline.
           REST: GET/POST /finance/templates, DELETE /finance/templates/{name}.
- [x] 6.12 Backoffice sección planes de inversión por usuario:
           Sección "Planes de inversión" en /users/{id}: tabla con posiciones, P&L actual por plan,
           botón eliminar por fila. REST: GET /finance/plans/{uid}, DELETE /finance/plans/{uid}/{name}.
- [x] 6.13 Reporte P&L horario por WA (intraday + total):
           finance_alerts._send_portfolio_pnl_hourly_wa() — por cada usuario con planes y wa_phone,
           envía WA con P&L del día ("hoy") y acumulada desde creación ("total") de cada plan.
           portfolio.calculate_plan_pnl() incluye intraday_pct (change_pct del día) en cada row.
           Cooldown configurable por usuario. Emojis bidireccionales: 🚀 arriba del umbral, ⚠️ abajo.
           Se omite si toda la P&L es < 0.05% (ruido de mercado cerrado). Llamada desde check().
- [x] 6.14 Config P&L por usuario editable desde backoffice:
           Tres campos nuevos en user_context_schema de FinanceAgent: plan_pnl_up_pct, plan_pnl_down_pct,
           plan_pnl_hours. finance_alerts._get_user_pnl_config() los lee via user_context.get_context(),
           con fallback a defaults globales (.env). Globales: FINANCE_PLAN_PNL_UP_PCT=5.0,
           FINANCE_PLAN_PNL_DOWN_PCT=-5.0, FINANCE_PLAN_PNL_HOURS=1. Clamp mínimo de 1h.
           Valores inválidos hacen fallback silencioso al global.
- [x] 6.15 Todas las alertas de finanzas configurables por usuario:
           _get_user_pnl_config reemplazado por _get_user_alert_config que cubre los 7 umbrales:
           dollar_gap_pct, btc_move_pct, stock_move_pct, briefing_hour, plan_pnl_up_pct,
           plan_pnl_down_pct, plan_pnl_hours. check() itera por usuario en todas las reglas,
           cooldown keys incluyen uid. user_context_schema extendido con 4 campos nuevos.
- [x] 6.17 Templates de inversión per-user:
           Eliminados los templates globales (/finance/templates). Cada usuario tiene
           su propio archivo finance_templates_{uid}.json con defaults hardcodeados
           (conservador/moderado/agresivo) si nunca personalizó. Nuevos endpoints
           GET/POST/DELETE /finance/plans/{uid}/templates en core. Backoffice: sección
           "Templates de inversión" bajo el agente finance en user_detail, separada
           visualmente de los campos del LLM context. Formulario inline con HTMX.
           Sidebar pierde ítem global "Templates inv."
- [x] 6.18 Ticker autocomplete en formulario de templates:
           GET /finance/tickers/popular — lista curada (22 instrumentos: CEDEARs, ETFs, cripto,
           commodities, FX) con cache 5min. GET /finance/tickers/search?q= — proxy Yahoo Finance
           search con debounce 280ms y cache 5min. Formulario de nuevo template rediseñado: filas
           dinámicas ticker+%, dropdown con curada agrupada por categoría al hacer focus, búsqueda
           en tiempo real al tipear. Validación suma=100% antes de guardar. Fix autocomplete:
           hideTimer compartido con clearTimeout, position:fixed sin scrollY, tmplAddRow() retorna
           input, foco con setTimeout(0).
- [x] 6.19 Ventana temporal configurable + desglose por ticker en P&L history:
           BACKEND: get_plan_pnl_history(plan, interval, start, end) con start/end opcionales
           clampeados a created_at. Retorna 3-tupla (series, trend, ticker_series) donde
           ticker_series mapea cada ticker a [{date, pnl_pct, contribution}]. Core server pasa
           ?start=&end= al portfolio. Backoffice proxy reenvía ambos params.
           FRONTEND: date range picker (desde/hasta, min=creación plan más antiguo). Drag-to-select
           en el gráfico via chartjs-plugin-zoom: arrastrar actualiza inputs de fecha automáticamente.
           Botón Restablecer vuelve al rango completo. Toggle "Desglose tickers": líneas por ticker
           con contribución ponderada, sin fetch (re-render desde cache). Métricas incluyen tabla
           de P&L propio + contribución por ticker. Timezone fix (forward-fill) para planes con
           mezcla de equity/cripto/commodity.
- [ ] 6.20 Ciclo proactivo de mejora de planes:
           `_proactive_json_extra_schema` + `_on_proactive_llm_data` + `handle_captured_reply`
           en FinanceAgent. El LLM proactivo recibe contexto de planes+P&L+perfil+noticias y
           puede sugerir modificaciones via campo "plan_proposals" en el JSON de respuesta.
           El usuario acepta/rechaza via request intent (WA o web). Se registra en plan_events.py.
           HOOKS en ProactiveMixin: _proactive_json_extra_schema (extiende JSON schema al LLM),
           _on_proactive_llm_data (procesa campos extra de la respuesta). _is_affirmative() parsea
           respuestas del usuario (sí/dale/ok/...). Auto-dedup contra intents activos por título.

- [ ] 6.21 Milestones en histograma P&L:
           plan_events.py — log de eventos de plan (suggestion/applied/rejected/manual_edit),
           almacenado en ~/.local/share/capitan/plan_events/{user_id}.json.
           Endpoint GET /finance/plan-events/{user_id} con filtros plan_name y since (ts Unix).
           Backoffice finance_pnl_history.html: chartjs-plugin-annotation@3, función loadMilestones()
           carga eventos y renderiza líneas verticales: amarillo=sugerencia, verde=aplicado,
           rojo=rechazado. Nearest-label matching para eje category.

- [x] 6.16 Histograma de P&L de planes a lo largo del tiempo (backoffice):
           Vista en backoffice que muestra evolución histórica del P&L de cada plan.
           FUENTE DE DATOS: precios históricos vía fc.get_price_at_date() / yfinance.history()
           desde created_at hasta hoy, frecuencia diaria.
           BACKEND:
             - portfolio.get_plan_pnl_history(plan, freq="1d") → list[{date, pnl_pct, per_position}]
               Calcula P&L ponderada para cada fecha entre created_at y hoy.
               Cachea hasta 1h (yfinance devuelve datos estáticos intradía).
             - GET /finance/plans/{uid}/history?plan=NAME — devuelve JSON con serie temporal.
               Soporta múltiples planes: ?plan=A&plan=B (o todos si se omite).
             - Tendencia: regresión lineal sobre la serie. Devuelta como pendiente (pct/día) + proyección 30d.
           FRONTEND (backoffice Jinja2 + Chart.js CDN):
             - Nueva sección en /users/{id} bajo "Planes de inversión".
             - Línea por plan (Chart.js line chart), escala % en Y, fechas en X.
             - Toggle para mostrar/ocultar planes individuales.
             - Línea punteada de tendencia (regresión + proyección).
             - Tooltip con valor exacto por fecha.
           TESTS:
             - get_plan_pnl_history: precio estático → P&L constante en cada punto.
             - get_plan_pnl_history: dos tickers con pesos distintos → ponderación correcta.
             - endpoint /history: retorna JSON con campo "series" + "trend".
             - tendencia: serie ascendente → pendiente positiva.

---

### FASE 7 - Agente Viajes
```
Objetivo: Asistente de planificación activa de viajes futuros
Estado:   COMPLETA (7.2 postergada por falta de docs centralizados)
Foco:     Planificación activa (itinerarios, qué llevar, visa, clima en destino).
          Grupo viajero variable por conversación (individual, pareja, familia).
          Documentos de viaje en modelo de usuario (ver 2.5.10 para gestión por voz).
```
- [x] 7.1  Casos de uso definidos: planificación activa de viajes futuros, grupo familiar
           variable, documentos en user model, clima en destino via geocoding
- [ ] 7.2  RAG sobre documentos de viaje (pasaportes, reservas, PDFs)
           Postergada: no hay documentos centralizados aún. Retomar cuando el usuario
           empiece a digitalizar reservas (emails, PDFs de hoteles/vuelos).
- [x] 7.3  Geocoding (geocoding.py): nombre de ciudad → lat/lon via Open-Meteo Geocoding API
           (gratuito, sin key, cache 24h). format_location() para contexto LLM.
- [x] 7.4  Documentos de viaje en User: campo documents [{type,country,expires,number,notes}],
           upsert_document(), remove_document(), expiring_documents(). API REST nueva.
- [x] 7.5  TravelAgent (travel_agent.py): geocoding → clima → documentos grupo → LLM.
           _extract_destination(): micro-LLM para extraer ciudad del texto.
           Grupo viajero resuelto por texto o todos los usuarios registrados.
- [x] 7.6  Alertas de documentos (travel_alerts.py): 3 tiers (30/90/180 días),
           cooldowns por (user, tipo, país, tier) via shared_state.

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

### FASE 9 - Coordinador Basado en Modelo
```
Objetivo: Reemplazar el router de reglas por un LLM coordinador capaz de descomponer
          requests complejos, rutear a múltiples agentes y agregar respuestas.
Estado:   COMPLETA
Deps:     FASE 3.2 (orquestador), FASE 3.3 (router de reglas como baseline),
          FASE 2.10 (contexto multi-turno), ≥2 agentes de dominio estables.
Cuándo empezar: cuando el router de reglas muestre limitaciones reales en uso diario
                (requests ambiguos, cross-domain, multi-paso). Puede superponerse con
                las últimas fases de dominio (FASE 6-7) una vez FASE 4-5 estén estables.
```

#### Por qué un modelo y no solo reglas

El router de reglas (FASE 3.3) funciona bien para intenciones simples y bien definidas.
Falla o requiere complejidad creciente ante:
- Ambigüedad: "prepará todo para salir" (¿persianas? ¿luces? ¿agenda?)
- Cross-domain: "¿debería llevar paraguas y tengo algo en la agenda mañana?"
- Multi-paso: "cuando llegue a casa, revisá el clima y si hace frío, encendé la calefacción"
- Contexto implícito: "¿y mañana?" (depende del turno anterior — requiere FASE 2.10)

Un LLM coordinador resuelve esto de forma natural, sin enumerar cada caso en código.
El beneficio escala con la cantidad de agentes: con 2 agentes, las reglas alcanzan;
con 5+, se vuelven un cuello de botella de mantenimiento.

#### Diseño del coordinador

El coordinador es un LLM que recibe:
```
[contexto de conversación]   ← últimos N turnos (FASE 2.10)
[utterance del usuario]
[catálogo de agentes]        ← nombre, descripción, ejemplos de queries válidas
```

Y produce un plan de ejecución estructurado:
```json
{
  "steps": [
    {"agent": "clima",  "query": "pronóstico mañana Buenos Aires", "depends_on": []},
    {"agent": "agenda", "query": "eventos de mañana",              "depends_on": []}
  ],
  "aggregation": "combinar pronóstico y agenda en una recomendación"
}
```

El orquestador (FASE 3.2) ejecuta los pasos (en paralelo cuando no hay dependencias),
recolecta los resultados y los devuelve al coordinador, que genera la respuesta final.

#### Opciones de modelo para el coordinador

| Opción | Modelo               | Latencia extra | Tradeoff                                      |
|--------|----------------------|---------------|-----------------------------------------------|
| A      | qwen2.5:7b (ya instalado) | +3-4s    | cero setup; puede sobrepensar en casos simples |
| B      | qwen2.5:3b (instalar)| +1-2s          | más rápido; validar calidad de routing         |
| C      | clasificador sklearn | <100ms         | limitado a intenciones vistas, no generaliza   |
| D      | híbrido C+B          | <100ms / +1-2s | mejor tradeoff; clasificador para casos simples, LLM para el resto |

Recomendación de arranque: **opción A** (reusa lo instalado, latencia conocida).
Objetivo de largo plazo: **opción D** — el clasificador absorbe el 80% de requests
simples en <100ms y el LLM entra solo cuando hay ambigüedad real.

#### Etapa A — Coordinador como router
- [x] 9.1  Definir formato del catálogo de agentes: nombre, descripción, 3-5 ejemplos de queries válidas
           Campo `examples` (5 queries por agente) en REGISTRY de agent_registry.py.
- [x] 9.2  Prompt del coordinador v1: utterance + catálogo → elige un agente + reformula query para ese agente
           coordinator.py (nuevo): `coordinate(text, conv_context)` → (agent_id, reformulated_query, latency_s)
           El contexto de conversación se inyecta para routing multi-turno correcto.
           El texto original sigue llegando al agente de dominio (Etapa B usará la query reformulada).
- [x] 9.3  Reemplazar router de reglas (FASE 3.3) con llamada al coordinador LLM
           server.py /process: conv se obtiene antes del coordinador para pasarle contexto;
           ProcessResponse agrega coordinator_query y coordinator_latency_ms para observabilidad.
           Impacto transversal: listen.py registra lat_coordinator en history.json;
           panel_latency.py muestra fila "Coordinador" dinámicamente.
- [x] 9.4  A/B test: precisión de routing coordinador vs. reglas sobre queries del historial real
           Benchmark 20 queries (2026-05-02):
           Keywords: 18/20 (90%) — falla en "mi pasaporte vence..." → travel (correcto: profile)
                                   y "debería llevar paraguas?" → haos (correcto: weather)
           Coordinador: 17/17 correctas en calls sin timeout (100%) — 3 timeouts por carga de Ollama
           Wins del coordinador: desambigua queries sin keywords claras; reformulación visible en logs.
- [x] 9.5  Medir overhead de latencia del coordinador; objetivo: que no supere 4s extra en warm
           Latencia warm del coordinador: ~3.5s (consistente con la llamada LLM del agente)
           Total warm estimado: ~11.5s (era ~8s). Overhead: +3.5s. ✓ Dentro del objetivo de 4s.
           Timeout aumentado a 20s para evitar falsos timeouts bajo carga concurrente.

#### Etapa B — Queries multi-agente
- [x] 9.6  Extender el plan de ejecución a N pasos con dependencias opcionales entre pasos
- [x] 9.7  Orquestador ejecuta pasos sin dependencias en paralelo (asyncio / ThreadPool)
- [x] 9.8  Coordinador recibe resultados de todos los agentes y genera respuesta unificada
- [x] 9.9  Prompt de agregación: sintetizar respuestas parciales en texto coherente, sin repetir cada una

#### Etapa C — Descomposición y corrección
- [x] 9.10 Detección de requests condicionales ("cuando X, hacé Y"): el coordinador genera un plan con condición explícita
- [x] 9.11 Manejo de falla de agente: el coordinador detecta error en resultado y reintenta o responde con degradación elegante
- [x] 9.12 Ciclo de clarificación: si el coordinador detecta ambigüedad irresoluble, genera una pregunta al usuario en vez de asumir

#### Etapa D — Optimización de latencia
- [x] 9.13 Evaluar qwen2.5:3b como coordinador: instalar, benchmark de routing vs. 7b
- [x] 9.14 Clasificador rápido para intenciones simples: entrenar con historial de requests reales (sklearn o reglas con score de confianza)
- [x] 9.15 Híbrido: usar clasificador cuando confianza > umbral configurable, coordinador LLM para el resto

#### Etapa E — Contexto por usuario por agente
```
Cada agente puede mantener un perfil de datos por usuario: preferencias aprendidas,
patrones de uso, información contextual persistente. El administrador define qué campos
recolecta cada agente y por cuánto tiempo. Cada usuario puede ver y gestionar la
información que cada agente guarda sobre él.
```
- [x] 9.16 `core/user_context.py` — almacena contexto estructurado en
           `~/.local/share/capitan/user_context/{user_id}/{agent_id}.json`.
           Cada campo: `{value, updated_at, ttl_days}`. Auto-expira campos en lectura.
           API interna: get_context(user_id, agent_id) / set_field(field, value) /
           delete_field(field) / get_all_for_user(user_id).
- [x] 9.17 Extensión de `agent_config.py` — campo `user_context_schema` por agente:
           lista de `{field, desc, type, ttl_days}` que define qué datos puede registrar
           el agente sobre cada usuario y por cuánto tiempo. Configurable en backoffice.
           Los tipos soportados: string, number, boolean, enum (con options).
- [x] 9.18 Inyección de contexto en dispatch: antes de llamar al agente, `server.py`
           carga el contexto vigente (campos no expirados) del usuario para ese agente
           y lo prepende al prompt como bloque estructurado. Sin contexto = sin overhead.
- [x] 9.19 Actualización de contexto post-interacción: el agente puede incluir
           `context_updates: [{field, value}]` en su respuesta estructurada.
           `server.py` persiste esas actualizaciones vía `user_context.py`.
           Cada agente decide qué aprende de la interacción (ej: clima aprende
           la ubicación preferida, inversiones aprende el perfil de riesgo).
- [x] 9.20 API REST para contexto de usuario:
           `GET /users/{id}/context` — contexto de todos los agentes (para backoffice),
           `GET/PATCH /users/{id}/context/{agent_id}` — contexto de un agente específico,
           `DELETE /users/{id}/context/{agent_id}/{field}` — eliminar un campo puntual.
- [x] 9.21 Backoffice `/agents/{id}/edit` — sección "Esquema de contexto de usuario":
           tabla editable de campos (nombre, descripción, tipo, TTL en días),
           botones agregar/eliminar campo, guardado vía PATCH al core.
           Un campo eliminado del schema no borra datos existentes (solo deja de inyectarse).
- [x] 9.22 Backoffice perfil de usuario `/users/{id}` — sección "Contexto en agentes":
           acordeón por agente, muestra campos vigentes con valor / última actualización /
           TTL restante en días. Botón editar valor (PATCH) y botón eliminar campo (DELETE).
           El propio usuario puede ver y controlar exactamente qué recuerda cada agente de él.

#### Etapa F — Intenciones persistentes y continuación proactiva

```
Las intenciones son una entidad de primer nivel (separada del user_context): representan
acciones que el usuario quiere hacer, monitoreadas por un agente entre sesiones.
Tienen ciclo de vida (pending → in_progress → done/cancelled), pueden disparar alertas
proactivas y son visibles en el backoffice como página propia (/intents).
Storage: ~/.local/share/capitan/intents/{user_id}.json
```
- [x] 9.23 `core/intent_state.py` — módulo propio (no anidado en user_context):
           `{intent_id, agent_id, user_id, title, description, status, context: dict,
           created_at, updated_at, expires_at, last_reminded_at, remind_after_days}`.
           API: `upsert()`, `get()`, `get_active()`, `get_active_for_agent()`,
           `update_status()`, `update_context()`, `delete()`, `get_all_needing_reminder()`,
           `get_all_active_across_users()` (vista admin).
- [x] 9.24 Detección de intenciones en agentes — agentes pueden devolver
           `(resp, action, {"context_updates": [...], "intent_updates": [...]})`.
           `_apply_agent_updates()` en `server.py` persiste ambos tipos.
           Backwards compatible: 3-tuple con lista directa sigue siendo context_updates.
- [x] 9.25 Retoma proactiva al inicio de sesión — `_build_agent_prefix()` en `server.py`
           inyecta contexto + intenciones activas como system message antes de cada llamada
           al agente (single-step y multi-step). El LLM las ve y las retoma naturalmente.
- [x] 9.26 Alertas proactivas de intenciones — `_alert_poller()` verifica
           `get_all_needing_reminder()` en cada ciclo; genera alerta y actualiza
           `last_reminded_at` para evitar spam.
- [x] 9.27 Backoffice: `/intents` como página de primer nivel con vista de todas las
           intenciones activas de todos los usuarios; widget en dashboard; acordeón en
           `/users/{id}` con intenciones activas por agente. Acciones: completar / eliminar
           vía HTMX. Nav link "🎯 Intenciones" en la barra lateral.

#### Etapa G — Proactividad de Agentes

```
Los agentes pueden generar intenciones sin esperar un comando del usuario.
Un scheduler asyncio en el core ejecuta proactive_check() por agente a intervalos
configurables. Por cada usuario registrado, el agente recibe su contexto vigente y
decide qué intenciones crear (lluvia prevista, evento próximo, precio en umbral, etc.).
El resultado se persiste vía intent_state.py; la inyección y entrega ya están resueltas
por Etapas E y F. No requiere infraestructura nueva: solo el scheduler y la implementación
en cada agente.

Triggers soportados en esta etapa: intervalo fijo en segundos.
Extensiones futuras: cron expressions, triggers por evento HAOS.
```
- [x] 9.28 `core/proactive.py` — `ProactiveScheduler`: registra agentes que declaren
           `proactive_schedule: int` (segundos de intervalo) y
           `async proactive_check(user_id: str, user_ctx: dict) → list[dict]`.
           Corre un loop asyncio independiente por agente: `sleep(interval)` → itera todos
           los usuarios registrados → llama `proactive_check` por usuario → persiste los
           intent_updates retornados via `intent_state.upsert()`.
           Anti-spam: si ya existe un intent activo con el mismo `title` para ese user+agent,
           no crea uno nuevo (el agente puede forzar actualización pasando `intent_id` explícito).
           Mantiene metadata `{last_run_at, next_run_at, last_intents_created, total_created}`
           por agente; expuesta vía `scheduler.status()`.
- [x] 9.29 `core/server.py` — wiring del scheduler en `lifespan()`: instanciar `ProactiveScheduler`,
           registrar agentes de `AGENTS` que cumplan el protocolo, lanzar
           `asyncio.create_task(scheduler.run_all())` al startup.
           `GET /proactive/status` → retorna `scheduler.status()` (dict por agent_id).
           `POST /proactive/{agent_id}/run` → trigger manual inmediato para ese agente,
           retorna `{agent_id, users_checked, intents_created}`.
- [x] 9.30 `core/clima_agent.py` — implementar proactividad:
           `proactive_schedule = 21600` (cada 6h).
           `proactive_check`: consulta Open-Meteo para hoy y mañana usando la ubicación del
           user_ctx (`preferred_location`) o la config default del agente.
           Genera intents según umbrales: precipitación diaria > 5mm o prob > 60% →
           `"⛈ Lluvia prevista — llevá paraguas"`; temperatura máxima > 35°C →
           `"🥵 Calor extremo (X°C) — hidratate"`;
           temperatura mínima < 3°C → `"🧊 Noche fría (X°C) — cerrá ventanas"`;
           viento > 50km/h → `"💨 Viento fuerte previsto"`.
           Un intent por tipo de alerta; no genera si ya existe uno activo con el mismo título.
- [x] 9.31 `core/agenda_agent.py` — implementar proactividad:
           `proactive_schedule = 3600` (cada 1h).
           `proactive_check`: consulta CalDAV del usuario (si está configurado); por cada
           evento que comience en las próximas 2h genera intent
           `"📅 <nombre evento> en X min (<hora>)"`.
           Deduplicación: guarda el `event_uid` de CalDAV en el `context` del intent;
           si ya existe un intent activo con ese `event_uid`, lo omite.
           No corre para usuarios sin CalDAV configurado (retorna `[]`).
- [x] 9.32 Backoffice `templates/agent_detail.html` — sección "Proactividad":
           Badge `🔄 proactivo` junto al nombre del agente si `agent.proactive_schedule` existe.
           Sección nueva con: intervalo declarado (ej: "cada 6h"), timestamp del último run,
           cantidad de intents creados en el último run, próximo run estimado.
           Botón "Ejecutar ahora" → `hx-post` → muestra resultado inline sin recargar.
- [x] 9.33 Backoffice `server.py` — proxy `GET /proactive/status` y
           `POST /proactive/{agent_id}/run` (retorna fragmento HTML con el resultado).
           `agent_detail_page()` llama `/proactive/status` y pasa `proactive_info[agent_id]`
           al template.
- [x] 9.34 `core/proactive.py` — filtro RBAC + control `proactive_enabled` por usuario:
           `_run_agent()` comprueba RBAC antes de llamar `proactive_check` para cada usuario.
           Lee campo `proactive_enabled` del contexto del usuario para ese agente (default True);
           si es `False`, omite al usuario silenciosamente.
- [x] 9.35 Backoffice `user_detail.html` + `server.py` — control total del usuario sobre
           proactividad: sección "Proactividad" con toggle opt-in/opt-out por agente (HTMX).
           "Contexto aprendido": botón eliminar por campo individual (HTMX, proxy ya existe).
           "Intenciones activas": agrupadas por agente, botones "Hecha" y "Cancelar" por intent
           (HTMX PATCH al proxy ya existente, la fila desaparece al confirmar).
           `user_detail_page()` recibe `proactive_status` del core.
- [x] 9.36 Backoffice `/agents` — lazy-load de columna "Accesible":
           `agents_page()` usa `/agents-meta` (5ms, sin connectivity checks) en lugar de `/agents` (28s).
           `/agents-meta` extendido con `desc`, `status`, `proactive_enabled`, `fancy_name`, `dynamic`.
           Columna "Accesible" muestra spinner en render inicial; HTMX GET a `/api/agents/{id}/reachable`
           carga el estado por fila en paralelo (~1-2s/fila).
           Nuevo endpoint `/agents/{id}/reachable` en core: chequea backends de un agente individual.
           Backoffice proxy `/api/agents/{id}/reachable` retorna fragmento HTML directamente.
- [x] 9.37 Backoffice `user_detail.html` — campos de `user_context_schema` siempre visibles y editables:
           Sección "Contexto por agente" usa `/agents-meta` para iterar schemas declarados.
           Agentes con schema: controles input/select pre-llenados (visibles aunque no haya valor).
           Agentes sin schema: read-only con botón eliminar (comportamiento original).
           `POST /users/{uid}/context/{agent_id}/{field}` persiste via PATCH al core.
- [x] 9.38 Fix: `proactive.py` — intent status del LLM no se persistía en `_persist_proactive_item()`.
           `_intent_state.upsert()` se llamaba sin el campo `status`, reseteando siempre a "active".
           El LLM marcaba intents como "done" con notify_message → WA se reenviaba cada hora.
           Fix: pasar `status=item.get("status")` en los casos advise y request. También: pasar
           `user_id` a `_send_wa_notification()` desde `_run_agent()` (inconsistencia con run_for_user_stream).
           Regresión cubierta en `tests/test_proactive_persist.py`.

---

### FASE 11 - Agente Amigo / Asesores Personales
```
Objetivo: Agente conversacional con quien charlar libremente, pedir consejos o consultar
          a un asesor especializado. Sin intención de acción — respuestas en lenguaje
          natural, tono informal, memoria entre sesiones.
Estado:   Pendiente
Deps:     FASE 1 (stack base) — puede implementarse en cualquier momento.
          FASE 2.5 (usuarios) deseable para asociar perfiles por persona.
          FASE 3 (orquestador) necesario para coexistir con múltiples agentes.
Nota:     El agente base (11.1–11.3) puede arrancar hoy: solo requiere un nuevo
          system prompt y lógica de dispatch. Los perfiles múltiples y la memoria
          persistente escalan naturalmente sobre esa base.
```

#### Por qué un "amigo" y no solo el LLM en modo libre

El LLM ya está disponible, pero sin contexto ni personalidad producirá respuestas
genéricas y frías. El valor del agente-amigo está en:
- **Personalidad consistente**: nombre, forma de hablar, valores propios
- **Memoria entre sesiones**: recuerda lo que hablaron la semana pasada
- **Perfiles múltiples**: podés charlar con "el amigo de siempre" o consultar
  al "asesor financiero" o al "coach de vida", cada uno con su expertise y tono
- **Contexto del usuario** (FASE 2.5): sabe quién habla y adapta la respuesta

#### Diseño de perfiles

Cada perfil es un YAML con:
```yaml
id: coach
nombre: Marcos
tono: directo y motivador, no da vueltas
expertise: [coaching de vida, productividad, hábitos]
prompt_extra: |
  Hacés preguntas concretas antes de dar consejos. No te quedás en lo abstracto.
  Usás ejemplos reales. Si el usuario no sabe qué quiere, lo ayudás a clarificarlo.
```

El agente carga el perfil y lo inyecta como system prompt enriquecido.
La selección de perfil puede ser explícita ("che, hablo con el coach") o
automática según el contexto del pedido.

#### Tareas
- [ ] 11.1  Agente conversacional base: system prompt de "amigo" en lenguaje natural,
            sin formato ACTION, respuestas libres. Dispatch activado cuando no hay
            intención domótica clara y el usuario quiere charlar.
- [ ] 11.2  Perfil del amigo: YAML configurable (nombre, tono, expertise, prompt_extra).
            Un perfil por defecto "amigo general" cargado al arrancar.
- [ ] 11.3  Detección de intención conversacional en el dispatcher: distinguir
            "prende la luz" (haos) de "che, cómo estás" o "necesito un consejo" (amigo).
- [ ] 11.4  Perfiles múltiples: registro de perfiles en YAML, selección por nombre
            explícito ("hablo con el coach") o por detección de tema.
- [x] 11.5  Memoria persistente entre sesiones: historial de conversaciones por
            (agent_id, user_id) en ~/.local/share/capitan/history_*.json, max 40 turnos,
            escritura atómica. GenericAgent inyecta historial al primer turno de cada sesión.
            Los datos nunca salen de la red local.
- [ ] 11.6  Asesores especializados: perfiles con expertise marcado y prompt enriquecido
            con contexto del área (finanzas, nutrición, coach de vida, etc.).
            El asesor puede combinar conocimiento propio del usuario (FASE 2.5)
            con su expertise: "sabiendo que invertís en acciones, te diría que..."
- [ ] 11.7  Integración con FASE 2.5: cada usuario registrado puede configurar
            su perfil de amigo/asesor preferido, persistido en su perfil de usuario.
- [ ] 11.8  Dashboard: panel o indicador en panel_agents mostrando el amigo activo
            y el perfil en uso cuando la conversación es con el agente-amigo.

---

### FASE 10 - Infraestructura de Inferencia Distribuida
```
Objetivo: Romper la asunción de que todos los modelos corren en un único Ollama local.
          Abstraer el cliente de inferencia para soportar múltiples nodos/backends dentro
          de la red, cada uno con hardware y modelos optimizados para distintos agentes.
Estado:   Pendiente
Deps:     FASE 8 (servidor dedicado operativo), FASE 3 (orquestador con agentes múltiples)
Cuándo empezar: cuando el primer servidor dedicado esté funcionando y aparezca la primera
                necesidad de hardware diferenciado por agente (ej: modelo 32b que no cabe
                en el mismo nodo que los modelos generales).
```

#### Por qué un único Ollama es una limitante

Un solo servidor Ollama comparte VRAM/RAM entre todos los modelos. Esto implica:
- Techo físico: no podés correr simultáneamente un modelo 32b y varios 7b en la misma GPU
- Acoplamiento de hardware: modelos con necesidades distintas (VRAM alta, CPU offload,
  quantización diferente) compiten por el mismo recurso
- Sin escala horizontal: si un agente está saturado, no podés agregar capacidad sin
  replicar todo el nodo
- Lock-in de framework: Ollama no es el único runtime; vLLM, llama.cpp server y TGI
  ofrecen mejor throughput o soporte para modelos específicos

#### Diseño: mesh de inferencia

```
core/inference_client.py     ← cliente agnóstico, API compatible OpenAI
core/node_registry.py        ← catálogo de nodos con health check

Nodos posibles en la red:
  ollama-principal  (RTX 4090, 24GB VRAM)  → modelos generales 7b-14b
  ollama-secundario (RTX 3060, 12GB VRAM)  → coordinator 3b, fallback
  vllm-node         (multi-GPU futuro)      → modelos 32b-72b
  cpu-node          (NAS / RPi)             → modelos livianos, emergencia
```

Config por agente (YAML o env), reemplaza el hardcoding actual:
```yaml
agents:
  finance:   {endpoint: "http://gpu-2:11434", model: "qwen2.5:32b"}
  coordinator: {endpoint: "http://gpu-1:8000", model: "qwen2.5:3b"}  # vLLM
  climate:   {endpoint: "http://gpu-1:11434", model: "qwen2.5:7b"}
  fallback:  {endpoint: "http://cpu-node:11434", model: "qwen2.5:7b"}
```

Todos los backends exponen API compatible OpenAI — el cliente es el mismo,
solo cambia la URL y el modelo.

#### Etapa A — Abstracción del cliente de inferencia
- [ ] 10.1  inference_client.py: cliente HTTP compatible OpenAI (Ollama, vLLM, llama.cpp server, TGI)
- [ ] 10.2  Config por agente en YAML: endpoint + model (reemplaza OLLAMA_URL hardcodeado en agent_registry.py)
- [ ] 10.3  Migrar todos los agentes existentes a inference_client.py sin cambios de lógica

#### Etapa B — Mesh de nodos
- [ ] 10.4  node_registry.py: catálogo de nodos con URL, modelos disponibles, tipo de hardware y estado
- [ ] 10.5  Health check periódico por nodo: disponibilidad, latencia media, modelos cargados en memoria
- [ ] 10.6  Routing agente → nodo: el orquestador consulta node_registry y elige el nodo óptimo disponible

#### Etapa C — Resiliencia
- [ ] 10.7  Fallback automático: si el nodo primario no responde, redirigir al nodo alternativo configurado
- [ ] 10.8  Circuit breaker por nodo: marcar como no disponible tras N fallos, recuperación automática con backoff
- [ ] 10.9  Cola de requests: encolar si todos los nodos del agente están saturados en lugar de devolver error

#### Etapa D — Observabilidad
- [ ] 10.10 Métricas por nodo: latencia p50/p95, tokens/s, requests en vuelo, errores
- [ ] 10.11 Panel en dashboard: estado del mesh, nodos activos, modelos cargados, latencia en tiempo real
- [ ] 10.12 Alerta si un nodo cae: notificación por WhatsApp (vía FASE 3.5) o TTS en el agente de voz

---

### FASE 12 - Backoffice Web
```
Objetivo: Panel web local para explorar y configurar toda la red de agentes sin tocar archivos
          ni endpoints crudos. Reemplaza el acceso directo a .env, logs y shared_state.
          Accesible desde cualquier dispositivo de la LAN (tablet, teléfono, laptop).
Estado:   COMPLETA
Deps:     FASE 3 (core API — ya completa). No requiere agentes futuros para arrancar.
          Cobra más valor cuando hay ≥3 agentes activos (FASE 5-6).
Cuándo:   Puede empezarse en cualquier momento. Recomendado después de FASE 5.
```

Stack elegido:
- Servicio FastAPI separado en :8080 (no acoplar admin al core de agentes)
- Jinja2 + Tailwind CDN + HTMX (sin build step, coherente con "todo Python, todo local")
- Server-Sent Events (SSE) para dashboard y log viewer en tiempo real
- Token de autenticación en .env, cookie de sesión httponly

#### Infraestructura base
- [x] 12.1  Nuevo servicio `backoffice/server.py` en :8080:
            FastAPI + Jinja2 templates + Tailwind CDN, layout base con sidebar de navegación
            y header con indicadores de estado (Ollama/HAOS/core up/down)
- [x] 12.2  Autenticación básica: `BACKOFFICE_TOKEN` en .env, cookie de sesión httponly.
            Sin auth no se expone .env ni shared_state al resto de la LAN
- [x] 12.3  Heartbeat de "ears": `listen.py` registra en /tmp/capitan/devices.json al arrancar
            y cada 60s (hostname, PID, estado, última actividad). Base para la sección Dispositivos.
- [x] 12.4  Systemd unit `capitan-backoffice.service` (user), arranca junto con core

#### Secciones del panel
- [x] 12.5  **Dashboard**: servicios activos (Ollama / HAOS / core / backoffice), última actividad
            (polling de `/tmp/capitan/history.json` + `/health`), latencias promedio de la sesión,
            alertas pendientes en cola. Vista principal al entrar.
- [x] 12.6  **Agentes**: tabla completa del registry (nombre, estado, keywords, descripción),
            toggle active ↔ planned sin reiniciar el core, enlace a docs/fuente de cada agente
- [x] 12.7  **Shared State**: tabla en tiempo real de todas las claves (vía `GET /shared-state`),
            TTL restante, valor, botón eliminar entrada. Auto-refresco via HTMX polling
- [x] 12.8  **Conversaciones**: listado paginado (vía `GET /conversations`), filtro por estado
            (active/closed/expired), ver turns completos de una conversación, cerrar manualmente
- [x] 12.9  **Estadísticas**: latencias p50/p95 por agente (STT/LLM/total), comandos por hora
            (gráfico temporal), agentes más usados, errores frecuentes. Fuente: history.json acumulado
- [x] 12.10 **Alertas**: reglas activas de cada agente con cooldown restante (desde shared_state),
            historial de últimas N alertas emitidas, botón "emitir alerta de prueba" para debug
- [x] 12.11 **Configuración**: editor de `.env` del core estructurado por sección
            (HAOS, Ollama, Clima, Alertas, Ubicación), validación de campos, guardar y recargar
            el provider/cliente sin reiniciar el proceso completo
- [x] 12.12 **Dispositivos**: lista de "ears" activos (desde devices.json heartbeat),
            hostname, estado, mic en uso, última actividad. Útil cuando hay múltiples instancias
            (laptop + tablet + RPi, etc.)
- [x] 12.13 **Usuarios**: stub integrado con FASE 2.5 — lista de usuarios registrados, rol,
            si tiene modelo de speaker entrenado, fecha de enrollment. Operativo cuando FASE 2.5 esté activa
- [x] 12.14 **Log viewer**: SSE con `journalctl --user -u capitan* -f` en tiempo real,
            filtro por servicio (core / ear / backoffice), color por nivel (INFO/WARN/ERROR)
- [x] 12.15 **Integraciones**: test de conexión on-demand a HAOS / Ollama / proveedores de clima,
            lista de entity_ids mapeados en ha_client.py, estado de modelos cargados en Ollama

---

### FASE 13 - Agente NotebookLM
```
Objetivo: Wrapper sobre NotebookLM — consultar notebooks, agregar fuentes y recibir respuestas
          desde voz o WA, sin salir de la red de agentes.
Estado:   Pendiente
Deps:     FASE 3.2 (orquestador), FASE 3.5 (WA — canal ideal para queries largas y URLs)
API:      No hay API oficial pública. Opciones en orden de preferencia:
          1. Cliente HTTP no oficial (reverse-engineered): más liviano, sin browser
          2. Playwright browser automation: más robusto ante cambios de API
          Elegir en 13.1 según estado actual de librerías disponibles.
Auth:     Google OAuth2 — device flow para el primer login, token refresh automático,
          credenciales persistidas en ~/.local/share/capitan/ (fuera del repo)
```
- [ ] 13.1  Evaluar stack de acceso: testear cliente HTTP no oficial (PyPI/GitHub) vs Playwright.
            Criterios: funciona con cuenta personal, soporta query + add_source, se mantiene activo.
            Documentar decisión y dependencias necesarias.
- [ ] 13.2  Autenticación Google OAuth2: device flow para primer login, refresh automático del token,
            credenciales en ~/.local/share/capitan/notebooklm_token.json (gitignored)
- [ ] 13.3  notebooklm_client.py: listar notebooks (id, título, nro de fuentes), obtener notebook por nombre/id
- [ ] 13.4  Query: preguntar a un notebook específico → respuesta con citas de fuentes
- [ ] 13.5  Gestión de fuentes: agregar URL, PDF local o texto plano a un notebook específico
- [ ] 13.6  Notebook activo en shared_state: configurar cuál se usa cuando no se especifica nombre,
            persistido cross-session en shared_state["notebooklm.active_notebook"]
- [ ] 13.7  NotebookLMAgent: implementar BaseAgent, keywords de dispatch, manejo de intención
            ("preguntá", "consultá", "qué dice", "agregá fuente", "notebook de X")
- [ ] 13.8  Comandos de voz: "preguntale al notebook de inversiones si GGAL vale la pena",
            "agregá esta URL al notebook de viajes", "qué dice el notebook sobre el ayuno"
- [ ] 13.9  Canal WA: soporte para queries largas (sin límite de audio), pegar URLs en el chat
            para agregarlas como fuente al notebook activo o a uno nombrado
- [ ] 13.10 Dashboard: panel en backoffice con lista de notebooks, notebook activo, última consulta
            y estado del token OAuth (válido / expirado / no configurado)

---

### FASE 14 - Gestión dinámica de agentes desde el backoffice
```
Objetivo: Hacer que status, keywords y configuración específica de cada agente sean editables
          desde el backoffice sin tocar código. Persiste en ~/.local/share/capitan/agents.json.
          Nuevos agentes aparecen automáticamente al declarar su config_schema.
Estado:   COMPLETA
Stack:    core/agent_config.py (nuevo) + backoffice/templates/agent_edit.html (nuevo)
Nota:     Cambios de config/keywords aplican en el próximo reinicio del core.
          Toggle de status aplica en runtime (el dispatcher lee el registry en cada llamada).
```
- [x] 14.1  `core/agent_config.py` — persistencia de config de agentes en JSON
            (singleton + atomic write, mismo patrón que users.py); migrate_from_env()
            migra valores de clima del .env al JSON on first run
- [x] 14.2  `core/agent_registry.py` — `get_registry()` que fusiona REGISTRY estático + overrides
            del JSON; dispatcher y agent_status() usan keywords/status efectivos
- [x] 14.3  `core/server.py` — 4 endpoints nuevos: GET /agents/{id},
            PATCH /agents/{id}/status, /agents/{id}/keywords, /agents/{id}/config;
            GET /agents enriquecido con config_schema, config y reachable (availability_url check)
- [x] 14.4  `core/agent.py` (HaosAgent) — config_schema (model, top_k_entities, max_retries),
            __init__ lee agent_config, availability_url → HAOS_URL/api/
- [x] 14.5  `core/clima_agent.py` (ClimaAgent) — config_schema (model, provider, lat, lon,
            location_name), __init__ con cadena agent_config > .env > default,
            availability_url → Open-Meteo; weather_providers.load_provider acepta name opcional
- [x] 14.6  `backoffice/templates/agents.html` — toggle HTMX real por fila, columna Accesible
            (●/—), columna Editar con link a /agents/{id}/edit
- [x] 14.7  `backoffice/templates/agent_edit.html` (nuevo) — form con status radio + indicador
            de conectividad, textarea de keywords, campos dinámicos según config_schema
- [x] 14.8  `backoffice/server.py` — toggle real (alterna active ↔ planned via PATCH al core),
            GET/POST /agents/{id}/edit con conversión de tipos para config

- [x] 14.9  `core/agent_config.py` — soporte para agentes dinámicos: `create_dynamic_agent()`,
            `delete_dynamic_agent()`, `is_dynamic()`; flag `dynamic: true` en agents.json
- [x] 14.10 `core/agent_registry.py` — `get_registry()` incluye agentes dinámicos del JSON;
            `is_static_agent()` protege de eliminación a los del REGISTRY hardcodeado
- [x] 14.11 `core/server.py` — POST /agents (crear dinámico), DELETE /agents/{id} (solo dinámicos);
            fix PATCH endpoints para usar get_registry() en lugar de REGISTRY estático
- [x] 14.12 `backoffice/templates/agent_edit.html` — sección RBAC: checkboxes de roles que tienen
            acceso al agente; aplica a estáticos y dinámicos; POST actualiza /rbac/roles/{role}
- [x] 14.13 `backoffice/templates/agent_new.html` — form de creación: id, nombre, icono, desc,
            status, keywords, roles por defecto
- [x] 14.14 `backoffice/server.py` — GET/POST /agents/new, DELETE /agents/{id} (HTMX),
            + RBAC aplicado al guardar edición y al crear; badge 'dinámico' en agents.html
- [x] 14.15 `core/generic_agent.py` (nuevo) — GenericAgent(agent_id): relay LLM puro con
            system_prompt y model configurables via agents.json; process() usa conv.context()
            y devuelve respuesta del LLM directamente, sin parseo ni llamadas a APIs externas
- [x] 14.16 `core/server.py` — carga GenericAgent para todos los agentes dinámicos al arrancar;
            POST /agents instancia y agrega a AGENTS; DELETE elimina de AGENTS;
            PATCH /config re-instancia GenericAgent para aplicar cambios sin reiniciar;
            agent_config.create_dynamic_agent acepta agent_type y system_prompt
- [x] 14.17 `backoffice/templates/agent_new.html` — sección System prompt (textarea required);
            agent_edit.html: type='text' en config_schema renderiza como textarea;
            backoffice/server.py: system_prompt en payload de POST /agents
- [x] 14.18 `core/generic_agent.py` — campo backend (select:[ollama]) en config_schema;
            model pasa a type='select' con options='ollama_models';
            process() despacha según backend; agent_config y server.py aceptan y persisten
            backend y model como config explícita en agents.json
- [x] 14.19 `backoffice`: sección Backend y modelo en agent_new.html (select Ollama + dropdown
            de modelos desde API); agent_edit.html: type='select' renderiza <select> con
            opciones estáticas o dinámicas (ollama_models); /devices redirige a /ear;
            ear.html: card Dispositivos integrada; base.html: quita nav link Dispositivos

---

### FASE 15 - Agente Multimedia
```
Objetivo: Control de música y video por voz en cualquier dispositivo del hogar.
          Fuente principal: YouTube Music (ytmusicapi + yt-dlp).
          Dispositivos: Smart TV y parlantes WiFi vía HAOS media_player;
          parlantes Bluetooth conectados a la laptop vía mpv + PipeWire.
Estado:   Pendiente
Deps:     FASE 3 (agent_registry), FASE 12 (backoffice)
Stack:    ytmusicapi (OAuth), yt-dlp (stream resolver), HAOS media_player service,
          mpv (local), PipeWire/pactl (BT sink routing)
```
- [ ] 15.1  `core/music_search.py` — integración ytmusicapi con OAuth persistente en
            `~/.local/share/capitan/ytmusic_oauth.json`. Funciones: search_tracks(query),
            search_albums(query), get_playlist(id). One-time OAuth flow documentado.
            Config en .env: `YTMUSIC_OAUTH_PATH`.
- [ ] 15.2  `core/stream_resolver.py` — dado un YouTube Music URL o video ID, usa yt-dlp
            en modo programático para obtener la mejor URL de stream de audio (para parlantes)
            o video+audio (para TV). Cachea el resultado 30min para evitar re-resolución.
- [ ] 15.3  Registro de dispositivos multimedia: `~/.local/share/capitan/media_devices.json`.
            Cada entrada: `{id, name, aliases, type: "haos"|"local", entity_id?, sink?}`.
            Ejemplos: tv del living (haos, media_player.samsung_tv), parlante cocina (local, sink BT).
            API CRUD: `GET/POST/PATCH/DELETE /media/devices`.
- [ ] 15.4  `core/multimedia_agent.py` — agente con intents: play(query, device),
            pause(device), resume(device), stop(device), volume(level, device), next_track(device),
            what_playing(device). Para tipo "haos": HAOS media_player service. Para tipo "local":
            mpv subprocess con `--audio-device=pipewire/<sink>` y control via IPC socket.
            Alias "todos" / "todo" → broadcast a todos los dispositivos activos.
- [ ] 15.5  Parsing de lenguaje natural: extraer intent + búsqueda + dispositivo destino de
            frases como "poné cumbia en el living", "subí el volumen de la tele", "qué está
            sonando", "pausá todo", "siguiente canción", "poné el playlist de los sábados".
            Dispositivo opcional: si falta, usar el último activo o el primero disponible.
- [ ] 15.6  Backoffice `/media`: estado actual por dispositivo (qué suena, volumen, progreso),
            controles rápidos por tarjeta (play/pause/vol/next), lista de dispositivos con
            estado online/offline. Actualización vía HTMX polling.
- [ ] 15.7  Backoffice configuración YouTube Music: sección en `/config` o `/integrations`
            con estado del token OAuth (válido / expirado / no configurado), botón para
            iniciar/renovar el flujo OAuth, instrucciones step-by-step.

---

### FASE 16 - Red de Nodos de Audio Multi-Ambiente

```
Objetivo: Distribuir la interfaz de voz por toda la casa. Los NSPanel Pro (Android, Termux)
          son los únicos puntos de captura y reproducción de audio. El ear corre en el SER9
          como servidor de audio puro (sin hardware local): recibe audio de los NSPanels,
          corre STT+TTS, delega al core, devuelve el WAV de respuesta.
          La laptop queda 100% desarrollo sin servicios.
Estado:   Pendiente
Deps:     FASE 1 (STT, TTS, Piper), FASE 3 (core/server.py, /process),
          FASE 21 (SER9 operativo — COMPLETA), FASE 2.5 (speaker_id), FASE 12 (backoffice)
Hardware: NSPanel Pro — Android 8.1, sounddevice/PortAudio, mic (pcmC0D0c) + speaker (pcmC0D0p).
          Termux + Python instalados. HA Companion como dashboard. ADB over WiFi.
          SER9 LXC — ear como servidor HTTP/WebSocket, STT+TTS sin /dev/snd local.
Nota:     Completa también 21.21 (decisión ear). Ver Anexo A.2 (origen).
```

#### Etapa A — Protocolo y nodo satélite básico
- [x] 16.1  Protocolo nodo↔servidor: especificación de mensajes WebSocket para streaming
            de audio en chunks. Estructura de chunk: `{node_id, room, chunk_b64, sample_rate}`.
            El nodo envía chunks post-wake-word; el core responde con texto de respuesta.
            Fallback: POST HTTP con el audio completo si WebSocket no disponible.
            Nota de diseño multi-nodo: el mensaje de handshake inicial (al conectar) debe
            incluir un campo `capabilities: {tts_local, mic_channels, hw_type}` para que el
            servidor adapte el formato de respuesta sin asumir el tipo de hardware. La respuesta
            TTS del servidor debe ser tipada: `{type: "tts_wav", wav_b64}` si el nodo no puede
            sintetizar, o `{type: "tts_text", text}` si puede (ej: RPi 5 con Piper local).
            NSPanel Pro declara `tts_local: false`; RPi 5 declara `tts_local: true`.
- [x] 16.2  `ear/satellite.py` — cliente ligero para el nodo satélite: detecta wake word
            con openWakeWord (modelo capitan.onnx), captura el comando, envía chunks al
            core vía WebSocket, recibe texto de respuesta y sintetiza TTS local con Piper.
            Sin STT ni LLM locales — toda la inferencia pesada queda en la laptop central.
            Configurable: CORE_WS_URL, ROOM, DEVICE_INDEX_MIC, DEVICE_INDEX_SPK.
- [x] 16.3  Registro de nodos en `ear/audio_server.py` + `GET /nodes` — registro en memoria:
            `{node_id, room, ip, last_seen, state: active|offline}`. Auto-registro en cada
            `POST /process-audio`; estado `offline` tras NODE_TTL (120s) sin actividad.
            Implementado en el audio_server (no en core/audio_nodes.py — ver nota de
            implementación). `capabilities` queda pendiente para Etapa D (16.11).
            Nota de diseño: este registry debe ser extensible para FASE 10 (inferencia
            distribuida tiene su propio node_registry.py). Considerar base común o
            interfaz unificada para evitar dos sistemas de health-check paralelos.
- [x] 16.4  `core/ws_audio.py` — servidor WebSocket `/ws/audio` en el core: recibe chunks
            del nodo, acumula y pasa al STT local (faster-whisper), llama internamente a
            `process()` con `source.room` del nodo, devuelve el texto de respuesta al nodo.
- [ ] 16.5  Propagación de `source.room` en el pipeline completo: historial,
            backoffice y dashboard muestran el ambiente de origen de cada comando.
            El campo ya existe en `source`; esta tarea lo hace obligatorio para nodos.
            Progreso: `audio_server.py` ya envía `source={room, channel:"ear"}` al core en
            cada comando. Falta verificar que historial/backoffice lo muestren.

#### Nota de implementación (Etapa A — MVP funcionando)

```
La Etapa A se implementó con HTTP (el fallback de 16.1), no WebSocket — más simple
y robusto para el MVP. Arquitectura real en producción:

NSPanel Pro (Termux)                      SER9 LXC
  ear/satellite.py                          ear/audio_server.py (:8766)
  - openWakeWord (capitan.onnx)             - faster-whisper STT
  - graba comando post-wake-word            - strip wake word prefix
  - POST /process-audio (WAV)        ──→    - POST core /process
  - reproduce WAV respuesta          ←──    - Piper TTS → WAV

audio_server.py vive en ear/ (no core/) porque reusa tts.py y el modelo de STT
del ear. El registry de nodos (16.3) está embebido en audio_server.py.
Latencia end-to-end: ~5s warm.

Dependencias NSPanel (Termux): python, portaudio, onnxruntime (pkg), openwakeword
(pip --no-deps + tqdm), Termux:API (APK GitHub, da permiso RECORD_AUDIO).
Ver docs/nspanel-setup.md para el bootstrap completo.

Pendiente Etapa A: feedback sonoro tras wake word (FASE 18) — sin él, el usuario no
sabe cuándo hablar y el STT captura ruido. Es el bloqueante de UX principal.
```

#### Etapa B — Output via Echo (sin hardware nuevo)
- [ ] 16.6  `core/response_router.py` — routear la respuesta al speaker correcto según
            `source.room`. Si el room tiene un Echo asignado: sintetizar TTS a WAV y
            reproducir via HAOS `media_player.play_media`. Si no: TTS local como ahora.
            Tabla de routing: `room → entity_id` configurable en `.env` o agents.json.
            Nota de diseño multi-nodo: si el nodo origen tiene `capabilities.tts_local: true`
            (RPi 5), enviar `{type: "tts_text"}` en lugar de WAV — el nodo sintetiza con
            Piper local, menor latencia y sin saturar el WebSocket con audio. El path Echo
            es ortogonal: aplica cuando el room tiene Echo asignado, independiente del nodo.
- [ ] 16.7  Backoffice `/rooms` — CRUD de ambientes: nombre, entity_id del Echo asignado,
            node_id del satélite si hay uno conectado. Tabla editable con estado en tiempo real.

#### Etapa C — Observabilidad y robustez
- [ ] 16.8  Health check periódico por nodo de audio: ping cada 30s desde el core,
            marcar offline si no responde en 3 intentos. Backoffice muestra estado en tiempo real.
- [ ] 16.9  Panel en dashboard zellij (`panel_nodes.py`): nodos de audio activos, ambiente
            del último comando, latencia STT+LLM por nodo, estado online/offline.
- [ ] 16.10 Guía de instalación del nodo satélite en nodo Linux genérico (referencia:
            Raspberry Pi OS): dependencias (Python, openWakeWord, Piper, pyaudio/sounddevice),
            configuración de audio (ALSA), systemd service con auto-reconexión, verificación
            end-to-end. Aplica a cualquier SBC Linux — RPi Zero 2W, RPi 5, etc.

#### Etapa D — Nodo potenciado: RPi 5 + pantalla oficial + ReSpeaker hat

```
Objetivo: Soportar un segundo tipo de nodo con más capacidades que el NSPanel Pro:
          mic array (4 canales, beamforming), TTS local con Piper, pantalla Linux (Chromium
          kiosk) y pleno control de ALSA. El protocolo de Etapa A es idéntico — la
          diferencia está en las capabilities declaradas en el handshake y en cómo el
          servidor y el nodo adaptan el pipeline de respuesta.
          NSPanel Pro sigue funcionando sin cambios.
Hardware: Raspberry Pi 5 (4GB+) + pantalla oficial 7" o 10" + ReSpeaker 4-mic hat (seeed).
          Alimentación directa (USB-C) o PoE hat para montaje en pared sin cables visibles.
```

- [ ] 16.11 Schema de capabilities para el handshake de registro. Definir el objeto canónico:
            `{hw_type: "nspanel"|"rpi5"|"generic", tts_local: bool, mic_channels: int,
            stt_local: bool, has_display: bool, display_type: "none"|"ha_companion"|"browser"}`.
            NSPanel Pro: `{hw_type:"nspanel", tts_local:false, mic_channels:1, stt_local:false,
            has_display:true, display_type:"ha_companion"}`.
            RPi 5: `{hw_type:"rpi5", tts_local:true, mic_channels:4, stt_local:false,
            has_display:true, display_type:"browser"}`.
            El servidor nunca bifurca por `hw_type` — solo por las capabilities booleanas.
            Retrocompatible: nodos que no envíen capabilities asumen el perfil NSPanel (defaults).
- [ ] 16.12 TTS bifurcado por capability en `ws_audio.py`: si `node.capabilities.tts_local`
            → enviar `{type:"tts_text", text:"..."}` al nodo (sintetiza con Piper local).
            Si no → enviar `{type:"tts_wav", wav_b64:"..."}` como hace hoy con NSPanel.
            El nodo NSPanel existente ignora mensajes de tipo desconocido — no se rompe.
- [ ] 16.13 `ear/satellite_rpi.py` — cliente satélite nativo Linux para RPi 5:
            mismo protocolo WS que `satellite.py`, declara capabilities RPi 5.
            Audio: ALSA / sounddevice apuntando al ReSpeaker (plughw:seeed4micvoicec,0),
            captura en 16kHz (ReSpeaker lo soporta nativamente — sin resampleo).
            TTS: Piper local con voz daniela, ffplay, igual que el ear actual.
            Configurable: CORE_WS_URL, ROOM, DISPLAY_URL (URL del dashboard HA para Chromium).
- [ ] 16.14 Setup guide RPi 5 + pantalla oficial + ReSpeaker hat:
            Raspberry Pi OS Lite (64-bit), seeed-voicecard driver, Piper TTS, Chromium en
            kiosk mode (`/etc/xdg/autostart/kiosk.desktop` apuntando a DISPLAY_URL),
            rotación de pantalla si montaje vertical, systemd service `capitan-satellite.service`
            con auto-reconexión al SER9. Verificación end-to-end: wake word → STT → LLM →
            TTS local → respuesta audible + dashboard HA visible.

#### Etapa E — Mejora continua de wake word en nodos (coherencia con flujo existente)

```
Objetivo: Integrar los nodos de audio al flujo de mejora de wake word que ya existe
          (muestras → métricas TP/FP → retrain supervisado desde backoffice).
          El uso diario alimenta el dataset orgánicamente; el retrain sigue siendo manual.
          Cierra el loop: nodo detecta → alimenta dataset → retrain → modelo vuelve al nodo.
Flujo existente: core/wakeword_trainer.py (positivos TTS+reales, negativos estáticos),
          /wakeword/train (supervisado), /users/{uid}/wakeword/samples, wakeword_metrics.json.
```

- [ ] 16.15 Métricas TP/FP orgánicas desde nodos: `audio_server.py` registra TP cuando el STT
            produce texto válido y FP cuando devuelve vacío/ruido tras un comando de nodo.
            Escribe en el mismo `wakeword_metrics.json` que lee el backoffice (audio_server
            corre en el SER9, co-ubicado con el core). Coherente con `_update_wakeword_metrics`
            de listen.py. El backoffice muestra las métricas de nodos sin cambios.
- [x] 16.16 Captura orgánica de muestras (gated): el nodo envía junto al comando el audio
            de la wake word que disparó la detección (el buffer pre-comando). `audio_server`:
            - FP (STT vacío) → guarda como hard negative en `wakeword/data/capitán/negative/`.
              Estos son ruido ambiente real — atacan directamente los falsos positivos.
            - TP (comando válido + speaker conocido) → sube como positivo real vía
              `/users/{uid}/wakeword/samples`. Gate anti-veneno: solo si STT no-vacío y speaker≠guest.
            El retrain (`/wakeword/train`) ya consume ambos directorios — sin cambios en el trainer.
- [x] 16.17 Propagación del modelo reentrenado a los nodos (pull): core expone
            `GET /wakeword/model` (devuelve capitan.onnx) y `GET /wakeword/model/version`
            (hash/mtime). `satellite.py` chequea la versión al arrancar y cada N minutos;
            si cambió, baja el modelo nuevo y recarga sin reiniciar. Cierra el loop de mejora
            continua: retrain en backoffice → nodos actualizados automáticamente.

---

### FASE 17 - Chat Visual con la Plataforma

```
Objetivo: Interfaz de chat web para conversar con los agentes escribiendo (sin voz),
          ver qué agente respondió y qué acción ejecutó, y gestionar el historial de
          conversaciones. Es la nueva landing del backoffice — el punto de entrada
          natural para el usuario antes de ir a las secciones de administración.
Estado:   COMPLETA
Deps:     FASE 12 (backoffice, COMPLETA), FASE 9 (coordinador, COMPLETA).
          Puede arrancarse ya. FASE 2.5 (usuarios) potencia el selector de usuario (17.6).
```

Stack: FastAPI + Jinja2 + Tailwind + JS nativo (sin HTMX en el chat — SSE requiere
fetch/ReadableStream). El core expone `/process/stream` (SSE); el backoffice hace relay
o el JS apunta directamente al core. Conversaciones persistidas en localStorage del browser.

#### Infraestructura de streaming
- [x] 17.1  **SSE en core** — `POST /process/stream`: misma lógica que `/process` pero
            llama a Ollama con `stream=True` y emite eventos SSE progresivos:
            `event: token` (fragmento de texto LLM), `event: action` (ACTION ejecutada +
            entity_id + resultado HAOS), `event: done` (fin + metadata: agente, latencias
            STT/LLM/total). El endpoint `/process` existente no se toca.
- [x] 17.2  **Relay en backoffice** — `POST /api/chat/send` recibe `{text, user_id}`,
            hace streaming del SSE del core y lo retransmite al browser como SSE.
            Maneja reconexión y errores de core (core caído → evento `error` al cliente).

#### UI de chat
- [x] 17.3  **Landing y layout** — `/` redirige a `/chat`. Template `chat.html` con layout
            pantalla completa (sin sidebar, sin max-w-6xl): columna de mensajes con scroll,
            input fijo al fondo, header mínimo con "⚓ Capitán" a la izquierda y link
            "Administración →" a la derecha que lleva a `/dashboard`.
- [x] 17.4  **Render en tiempo real** — burbuja del usuario aparece al instante al enviar.
            Burbuja del agente se construye token a token via SSE. Al recibir `event: action`,
            agregar chip de metadata debajo de la burbuja (agente, acción ejecutada, latencia);
            chip empieza colapsado, expandible al hacer click.
- [x] 17.5  **Persistencia local** — turnos guardados en `localStorage` del browser.
            Al cargar `/chat`, los últimos N turnos se restauran en pantalla. Botón
            "Nueva conversación" limpia el historial local y reinicia el contexto.

#### Gestión de conversaciones
- [x] 17.6  **Selector de usuario activo** — dropdown en el header del chat con los usuarios
            registrados (llamada a `/users` del backoffice). El `user_id` seleccionado se
            envía con cada mensaje al core. Selección persistida en `localStorage`.
- [x] 17.7  **Panel lateral de historial** — botón "Historial" colapsable en el chat.
            Lista las últimas conversaciones del core (`GET /conversations`), click en una
            muestra los turnos anteriores en modo lectura (no se puede continuar, solo leer).
- [x] 17.8  **Exportar conversación** — botón en el header. Genera un JSON con los turnos
            de la sesión actual y lo descarga via `Blob + URL.createObjectURL`. Alternativa:
            botón "Copiar como markdown" para pegar en notas.
- [x] 17.9  **Persistencia de conversaciones en disco** — `ConversationManager` guarda las
            conversaciones en `~/.local/share/capitan/conversations.json` al crear/actualizar/cerrar
            cada conversación. Al iniciar el core, carga el archivo y restaura el historial completo.
            Los turnos sobreviven reinicios del proceso.

---

## PIPELINE ACTUAL (para referencia rápida)

```
[ear/listen.py]
[MIC hw:1,0 44100Hz]
        ↓
[resampleo scipy: up=160, down=441 → 16000Hz]
        ↓
[faster-whisper small, int8, CPU]  ~4.6s
        ↓
[HTTP POST localhost:8765/process]  ~10ms overhead
        ↓
[core/server.py — FastAPI]
        ↓
[qwen2.5:7b via Ollama :11434]     ~3.5s
        ↓
[parser ACTION: domain.service | entity_id: X]
        ↓
[HAOS REST API :8123]
        ↓
[ear/listen.py]
        ↓
[Piper TTS respuesta → ffplay]
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
source ~/home-agents-env/bin/activate

# Iniciar sistema completo (recomendado)
systemctl --user start capitan-core   # 1. core primero
systemctl --user start capitan        # 2. ear después
curl http://localhost:8765/health     # verificar

# Dashboard interactivo (alternativa a systemd)
cd ~/workspace/home-agents/core && uvicorn server:app --host 127.0.0.1 --port 8765
bash ~/workspace/home-agents/ear/dashboard.sh

# Logs
journalctl --user -u capitan-core -f
journalctl --user -u capitan -f

# Test directo del core (sin ear)
curl -X POST http://localhost:8765/process \
  -H 'Content-Type: application/json' \
  -d '{"text":"prende la luz"}'

# Test TTS
python ~/workspace/home-agents/ear/tts.py

# Test parser LLM + HA (sin servidor)
python ~/workspace/home-agents/core/agent.py

# Debug wake word scores en tiempo real
python ~/workspace/home-agents/ear/wakeword/debug_scores.py

# Generar samples de wake word
python ~/workspace/home-agents/ear/wakeword/generate_samples_multi.py

# Sync issues con GitHub
python ~/workspace/home-agents/scripts/sync_issues.py

# Actualizar submodules
git -C ~/workspace/home-agents submodule update --remote
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

### FASE 18 - Mejoras de UX de Audio

```
Objetivo: Mejorar la experiencia de interacción por voz: feedback sonoro y visual al
          detectar la wake word, distinguiendo cada estado del pipeline. Aplica a los
          nodos NSPanel (FASE 16). Duck de volumen para la laptop/legacy.
Estado:   EN CURSO (18.1 + 18.3 completas; 18.2 pendiente para laptop)
Deps:     FASE 1 (pipeline base, COMPLETA), FASE 16 (nodos de audio).
```

- [x] 18.1  **Sonido de confirmación en wake word** — beep/chime de éxito (campana
            ascendente C5→G5 con armónicos, ~420ms) en `ear/assets/wakeword_ack.wav`.
            En `satellite.py` se reproduce tras detectar la wake word, antes de grabar.
            En Android se para el input stream durante el playback (OpenSLES no permite
            input+output simultáneos) y se reanuda para grabar el comando.

- [ ] 18.2  **Duck de volumen durante grabación** — al detectar wake word, bajar el
            volumen del sistema al mínimo posible (o mutear) antes de grabar el comando,
            y restaurarlo al nivel previo al terminar. Usar `pactl set-sink-volume` para
            control de PulseAudio/PipeWire. Debe detectar el nivel actual, bajar, grabar,
            y restaurar incluso si la grabación falla o el pipeline lanza excepción
            (try/finally). Implementar en `ear/listen.py` (laptop/legacy).

- [x] 18.3  **Indicador visual de estado en el nodo** — `ear/satellite_ui.py`: barra fina
            overlay (Termux:GUI) full-width en el borde superior, sobre HA Companion, que
            cambia color/animación por estado: listening=shimmer azul lento, wake=verde,
            recording=ámbar, waiting=respiro cian rápido, speaking=azul. Da feedback de
            "qué está pasando" sin estorbar la UI de HA. Degradación elegante si no hay
            Termux:GUI. Nota: los overlays de Termux:GUI no renderizan layouts anidados,
            por eso es una barra única animada por color (no segmentos espaciales).

#### Nota de implementación (calidad de audio del NSPanel)

```
El mic del NSPanel Pro capta muy bajo (RMS voz ~1000-1200, ruido ~25) con el preset
genérico de PortAudio (sin AGC). Mitigaciones implementadas en audio_server.py:
  - Normalización RMS (target 3500, gain hasta 30x) ANTES del STT
  - vad_filter de Whisper SOBRE el audio normalizado (aísla voz, descarta ruido)
  - condition_on_previous_text=False, no_speech_threshold=0.6 (anti-alucinación)
Y en satellite.py:
  - Gate de energía antes del wake word (silencio no scorea → sin falsos positivos)
  - Descarte de comandos casi-silenciosos antes de enviar
Pendiente/futuro: AGC nativo de Android (termux-microphone-record / preset
VOICE_RECOGNITION de OpenSLES) o nodo RPi 5 + ReSpeaker (FASE 16 Etapa D) para
calidad de captura superior.
```

---

### FASE 19 - Mejoras de Canal WhatsApp

```
Objetivo: Conversaciones más naturales y ricas por WhatsApp — respuesta inline a intents
          con diálogo pendiente, auto-cierre de notificaciones, y mensajes con media/links.
Estado:   COMPLETA
Deps:     FASE 3.5 (integración WA, COMPLETA), FASE 9 (coordinador, COMPLETA).
```

- [x] 19.1  **Reply-as-response para intents con diálogo** — cuando el core genera una
            respuesta que requiere input del usuario (confirmación, dato faltante, pregunta),
            guardar el `message.id` de WA del mensaje enviado en el contexto de la conversación
            (`conversation.pending_wa_msg_id`). En `wa/index.js`, al recibir un mensaje con
            `msg.hasQuotedMsg`, resolver el ID del mensaje citado y compararlo con el
            `pending_wa_msg_id` de las conversaciones activas; si coincide, enrutar ese
            mensaje como continuación del intent pendiente (no como nuevo intent).
            El core debe exponer el flag `needs_reply: true` en la respuesta `/process`
            cuando el agente espera input adicional.

- [x] 19.2  **Auto-confirmar notificaciones de solo-aviso** — cuando el core responde con
            `needs_reply: false` (aviso sin acción requerida del usuario), el adaptador WA
            envía automáticamente una reacción ✅ o un reply breve "ok" al mensaje original,
            marcando visualmente que el intent fue procesado. Implementar en `wa/index.js`
            usando `msg.react("✅")` como primera opción (más limpio); fallback a reply "ok"
            si la reacción falla. El flag `needs_reply` también aplica a intents de tipo
            alerta/proactivo enviados desde el core al usuario.

- [x] 19.3  **Mensajes ricos en WhatsApp** — para respuestas que lo ameriten, incluir media:
            - Link preview automático: si el texto contiene una URL, enviar via `client.sendMessage`
              con `linkPreview: true` (whatsapp-web.js lo genera solo).
            - Imagen adjunta: si el agente devuelve un `media_url` o `image_path` en la respuesta,
              cargar con `MessageMedia.fromUrl()` o `MessageMedia.fromFilePath()` y enviar
              antes o junto al texto.
            - Formato markdown WA: negrita `*texto*`, monoespaciado ` ```código``` `, listas `- item`.
              El core formatea la respuesta según canal (`source.channel == "whatsapp"`) usando
              helpers en `wa_formatter.py` (nuevo). Los canales voz/web no se ven afectados.
            - Casos concretos: clima → imagen del ícono meteorológico del día; inversiones →
              tabla de cotizaciones en monoespaciado; agenda → lista formateada de eventos.

Estado:   COMPLETA

---

### FASE 20 - Agente MercadoLibre

```
Objetivo: Búsqueda, benchmark, recomendación y seguimiento de precios en ML
          via API pública + OAuth 2.0 para operaciones autenticadas.
          Flujo conversacional multi-turno hasta encontrar el producto buscado.
Estado:   COMPLETA
Deps:     FASE 9 (coordinador, COMPLETA), FASE 6 (patrón agente+alertas, COMPLETA),
          FASE 19 (mensajes ricos WA, deseable para output).
Site:     MLU (Uruguay) por defecto; configurable via ML_SITE en .env (MLA, MLB, etc.)
```

#### Etapa A — Cliente público y búsqueda básica

- [x] 20.1  **Cliente ML público** (`ml_client.py`) — wrapper sobre la API pública de ML sin auth:
            `search(query, site, filters)` → lista de items paginada;
            `get_item(item_id)` → detalle completo (precio, condición, stock, vendedor, envío, fotos);
            `get_description(item_id)` → texto completo del producto;
            `get_seller(user_id)` → reputación, nivel de ventas, ubicación.
            Cache por defecto 10min (configurable); respeta rate limits ML (burst 10 req/s).
            Site configurable vía parámetro o `ML_SITE` en `.env`; default `MLU`.

- [x] 20.2  **Parsing de intents de búsqueda** — el LLM extrae de la consulta:
            `query` (término libre), `price_max`, `price_min`, `condition` (new/used/all),
            `category_hint` (texto libre → resolver a category_id vía `/sites/{site}/categories`),
            `free_shipping` (bool). Prompt específico de extracción (micro-LLM, similar a
            `_extract_destination()` en travel_agent.py). Sin categoría explícita, buscar en todo ML.

- [x] 20.3  **Benchmark de resultados** — dado el resultado de `search()`, generar tabla comparativa:
            precio, vendedor (nick + nivel), reputación (verde/amarillo/naranja/rojo), envío gratis,
            cantidad vendida, ubicación, link corto (permalink). Ordenar por score ponderado
            (precio normalizado 40%, reputación vendedor 30%, ventas 20%, envío 10%).
            Formato texto adaptado al canal: tabla monoespaciada para WA/chat, lista para voz.

- [x] 20.4  **Recomendación justificada** — el agente elige el mejor ítem del benchmark y
            genera una recomendación en lenguaje natural explicando por qué (precio justo,
            vendedor confiable, envío incluido, etc.). Si ningún ítem supera un umbral de
            calidad mínima (reputación < verde o precio outlier), lo indica y sugiere refinar
            la búsqueda. Respuesta voz: 2-3 oraciones. Respuesta WA/chat: párrafo + link.

#### Etapa B — Flujo conversacional multi-turno

- [x] 20.5  **Contexto de búsqueda por conversación** — `MLSearchContext` en `shared_state`
            por `source_key`: guarda la última query, filtros activos, página actual, y lista
            de items mostrados (referenciados por índice 1..N para follow-ups).
            Permite: "mostrá más" → página siguiente; "el segundo" → detalle del ítem 2;
            "filtrá por nuevo" → rerun con `condition=new`; "más barato" → rerun con
            `price_max` ajustado al mínimo encontrado; "seguí buscando" → nueva query derivada.

- [x] 20.6  **Refinamiento iterativo** — el agente detecta intents de refinamiento:
            `show_more`, `filter_update`, `item_detail`, `restart_search`.
            Para `item_detail`: llama `get_item()` + `get_description()` y resume en 3-4 puntos
            clave (qué incluye, garantía, ubicación vendedor, tiempo de entrega estimado).
            Para `filter_update`: reutiliza el contexto, aplica el filtro nuevo, resetea página.

#### Etapa C — Seguimiento de precios

- [x] 20.7  **Tracker de precios** (`ml_price_tracker.py`) — persistencia en
            `~/.local/share/capitan/ml_prices.json`. Estructura por usuario:
            `{user_id: [{item_id, title, target_price, snapshots: [{ts, price}], alert_sent}]}`.
            Comandos: "seguí el precio de este" (ítem del contexto actual), "dejá de seguir X",
            "¿cómo está el precio de lo que seguís?". El `item_id` se resuelve desde el contexto
            de búsqueda activo o por título si el usuario lo describe.

- [x] 20.8  **Alertas de precio** — el tracker tiene método `check()` registrado en el sistema
            de alertas existente (`alert_queue.py`): si precio actual < (precio_snapshot_anterior × (1 - ML_PRICE_DROP_PCT))
            → emite alerta "{title} bajó X% — ahora ${precio}". Umbral default 5% vía
            `ML_PRICE_DROP_PCT` en `.env`. Cooldown 24h por ítem para no repetir alertas.
            Chequeo cada hora junto al poller de alertas del core.

- [x] 20.9  **Seguimiento de búsqueda guardada** — además de items individuales, permitir
            guardar una query completa (ej: "notebook RTX 4060 hasta $3000"). Cada chequeo
            corre la búsqueda, compara contra el mejor precio previo registrado, y alerta si
            aparece un ítem nuevo más barato que el mínimo histórico. Útil para productos
            sin item_id estable (stock cambiante, varios vendedores).

#### Etapa D — OAuth y operaciones autenticadas

- [x] 20.10 **Registro de app ML** — proceso de setup único documentado:
            1. Crear app en https://developers.mercadolibre.com.ar → obtener `client_id` y `client_secret`.
            2. Configurar redirect URI: `http://localhost:8766/ml/callback` (puerto separado del core).
            3. Agregar `ML_CLIENT_ID`, `ML_CLIENT_SECRET` a `core/.env`.
            Scope requerido: `read` (para búsqueda autenticada y wishlist), `offline_access` (refresh).
            Sin estas vars, el agente opera en modo público sin OAuth (degradación limpia).

- [x] 20.11 **OAuth 2.0 Authorization Code flow** (`ml_auth.py`) — al solicitar auth:
            1. Generar URL de autorización ML y enviar al usuario por WA/voz/chat.
            2. Levantar servidor temporal `http://localhost:8766/ml/callback` con `http.server`
               (solo durante la ventana de auth, máx 5min).
            3. Capturar `code` del redirect, intercambiar por `access_token` + `refresh_token`
               via POST a `https://api.mercadolibre.com/oauth/token`.
            4. Persistir tokens en `~/.local/share/capitan/ml_token_{user_id}.json` (gitignored).
            Auto-refresh: si `access_token` vence (6h), usar `refresh_token` (180 días) transparentemente.

- [x] 20.12 **Operaciones autenticadas** — con token válido:
            `get_my_orders()` — historial de compras del usuario (útil para "¿ya compré esto antes?");
            `get_wishlist()` — items guardados del usuario en ML;
            `add_to_wishlist(item_id)` — guardar ítem desde el flujo conversacional.
            Si el usuario no autenticó, operaciones degradan a modo público con aviso.

- [x] 20.13 **oauth-app Cloud Run** — migración del servidor OAuth temporal (local :8766) a
            servicio permanente en `capitan.blasi.ar` (repo `home-agents-oauth`). App FastAPI que
            gestiona flujos ML y MP: recibe callback, intercambia code por tokens, guarda
            temporalmente con `short_code` (TTL 5 min), notifica al bot via WA Cloud API.
            Estado: elimina el servidor temporal en core; oauth-app es el punto de entrada público.

- [x] 20.14 **Backoffice: fallback de token por short_code** — cuando WA falla (ej: token 401),
            el token queda disponible en el oauth app por `GET /tokens/{short_code}`.
            Nuevo endpoint `POST /auth/{service}/fetch-shortcode` en `backoffice/server.py`:
            llama al oauth app y persiste el token en `~/.local/share/capitan/{svc}_token_{uid}.json`.
            UI en `agent_edit.html`: botón "Recuperar por short_code" (indigo) en la sección OAuth2
            de cada usuario del agente; los dos formularios (short_code y manual) se muestran
            exclusivos entre sí. El short_code aparece en los logs del oauth app y en la página de
            confirmación de ML.

Estado:   COMPLETA

---

### FASE 21 - Consolidación en SER9 (Paso Intermedio)
```
Objetivo: Mover toda la infraestructura de producción a la Beelink SER9 Pro.
          La laptop queda como entorno de desarrollo puro (sin servicios corriendo).
          Misma restricción de modelo 7B que la configuración actual.
          HAOS migra desde el PC viejo dedicado al SER9.
Estado:   Pendiente
Hardware: Beelink SER9 Pro — AMD Ryzen AI 7 HX 255, 32GB DDR5, Radeon 780M (RDNA 3)
Stack:    Proxmox VE → VM HAOS + LXC Ubuntu privilegiado (core + backoffice + wa + Ollama)
Nota:     Stepping stone a FASE 8 (servidor con GPU discreta). No escala modelos: sigue en 7B.
```

#### Arquitectura objetivo

```
SER9 (Proxmox VE)
├── VM: HAOS                     — imagen oficial, bridge LAN → IP real (192.168.68.101)
└── LXC Ubuntu privilegiado      — todos los servicios home-agents
    ├── core                     — FastAPI :8765
    ├── backoffice               — FastAPI :8080
    ├── wa                       — Node.js (whatsapp-web.js)
    ├── ear                      — ⚠ PENDIENTE (ver 21.21)
    └── ollama                   — CPU + ROCm 780M vía /dev/kfd + /dev/dri passthrough

Laptop → desarrollo puro (git, editor, deploy vía SSH)
```

LXC privilegiado (no VM) para que el passthrough de /dev/kfd + /dev/dri/renderD128 (ROCm)
y /dev/snd (audio ALSA, si corre el ear) sea directo y sin complejidad de IOMMU de APU.

#### Etapa A — Proxmox y red

- [x] 21.1  Instalar Proxmox VE en el SER9 (ISO oficial, bare metal).
            IP estática en la interfaz física del host PVE.
            Hostname: `capitan`, accesible como `capitan.local` (mDNS) o por IP fija.
- [x] 21.2  Crear bridge `vmbr0` sobre la interfaz física.
            El bridge da a las VMs y LXCs IP real en la LAN (sin NAT).
            Reservar IP del HAOS VM en el router (DHCP reservation por MAC → 192.168.68.101).
- [x] 21.3  SSH desde laptop configurado: clave pública copiada al host PVE y al LXC.
            Alias en `~/.ssh/config`: `Host capitan` → IP fija del LXC.

#### Etapa B — VM de HAOS

- [x] 21.4  Backup completo del HAOS actual: Settings → System → Backups → Download .tar.
- [x] 21.5  Crear VM en Proxmox con imagen oficial HAOS:
            Descargar `haos_ova-*.qcow2` (o usar Proxmox Helper Scripts — tteck).
            VM con red en `vmbr0` → IP real en LAN → reservar 192.168.68.101 por MAC.
- [x] 21.6  Restaurar el backup en el nuevo HAOS.
            Verificar: integraciones activas, entity_ids idénticos, Long-Lived Token funcionando.
            Smoke test: `curl http://192.168.68.101:8123/api/` con el token del .env.
- [x] 21.7  Autostart de la VM: Options → Start at boot → Yes.
- [x] 21.8  Apagar el PC viejo (solo tras confirmar 21.6 completo y token funcionando).

#### Etapa C — LXC Ubuntu privilegiado

- [x] 21.9  Crear LXC privilegiado (Ubuntu 24.04) en Proxmox:
            RAM: 12GB, cores: 6, storage: 40GB mínimo.
            Red en `vmbr0` → IP fija (ej: 192.168.68.102).
            `features: nesting=1` (necesario para systemd --user).
            Autostart: Yes.
- [x] 21.10 Pasar dispositivos GPU al LXC (en `/etc/pve/lxc/<id>.conf` en el host PVE):
            ```
            lxc.cgroup2.devices.allow: c 226:* rwm
            lxc.cgroup2.devices.allow: c 234:0 rwm
            lxc.mount.entry: /dev/dri dev/dri none bind,optional,create=dir
            lxc.mount.entry: /dev/kfd dev/kfd none bind,optional,create=file
            ```
            (Solo relevante si se confirma ROCm — ver 21.13/21.14.)
- [x] 21.11 Instalar en el LXC: Python 3.13, Node 18, git, ffmpeg (incluye ffplay), build-essential.
            Instalar Piper: descargar binario v1.2.0 + voces en `~/.local/share/piper/`.
            Crear `~/home-agents-env` (venv).

#### Etapa D — Ollama en el LXC

- [x] 21.12 Instalar Ollama en el LXC (`curl -fsSL https://ollama.ai/install.sh | sh`).
            Pull `qwen2.5:7b`. Systemd unit generada automáticamente.
- [x] 21.13 Benchmark CPU-only como baseline:
            `time ollama run qwen2.5:7b "responde solo: hola"` → latencia warm.
- [x] 21.14 Intentar ROCm 780M en el LXC:
            Instalar ROCm 6.x dentro del LXC. Verificar visibilidad de `/dev/kfd` y `/dev/dri/renderD128`.
            Si el chip es gfx1151 (Strix Point): puede necesitar `HSA_OVERRIDE_GFX_VERSION=11.0.0`.
            Re-benchmarkar. Si latencia warm < 2s y estable → mantener ROCm. Si no → CPU-only.
- [x] 21.15 Documentar resultado del benchmark y decisión ROCm en NOTAS.
            Resultado: CPU-only 27.5s | ROCm gfx1103 (780M) 13.3s — 2x mejora.
            Decisión: mantener ROCm con HSA_OVERRIDE_GFX_VERSION=11.0.0 en ollama.service.d/rocm.conf.
            /dev/kfd major 511 (no 234). chmod 666 /dev/kfd necesario al boot.

#### Etapa E — Migración de home-agents al LXC

- [x] 21.16 Clonar `home-agents` con submodules en el LXC:
            `git clone --recurse-submodules git@github.com:mblasi/home-agents.git ~/workspace/home-agents`
            Instalar deps Python: `pip install -r core/requirements.txt`
            Instalar deps Node: `npm install` en `ear/wa/` (o donde esté el cliente WA).
- [x] 21.17 Crear `core/.env` en el LXC:
            `OLLAMA_URL=http://localhost:11434`
            `HAOS_URL=http://192.168.68.101:8123`
            Resto de vars: copiar desde la laptop (HAOS_TOKEN, BACKOFFICE_TOKEN, etc.).
- [x] 21.18 Instalar y habilitar systemd user units: `capitan-core.service`, `capitan-backoffice.service`.
            `loginctl enable-linger <user>` para que las units arranquen sin sesión activa.
            Smoke test: `curl http://localhost:8765/health` desde el LXC.
- [x] 21.19 Levantar el cliente WA (`node ear/wa/index.js` o como esté estructurado),
            escanear QR, verificar reconexión automática y respuesta a mensajes.
- [x] 21.20 Test end-to-end desde la laptop:
            `curl -X POST http://capitan.local:8765/process -H 'Content-Type: application/json' -d '{"text":"prende la luz"}'`
            Backoffice accesible en `http://capitan.local:8080`.

#### Etapa F — Ear (decisión tomada)

- [ ] 21.21 **Decisión**: el ear corre en el LXC del SER9 como servidor de audio — SIN hardware
            de audio local (no mic, no speaker, no /dev/snd). Es un proceso servidor que:
            - Recibe audio (WAV/chunks) desde los NSPanel Pro vía WebSocket o HTTP
            - Corre STT (faster-whisper) sobre ese audio
            - Llama al core (/process) y obtiene respuesta
            - Sintetiza TTS (Piper) y devuelve el WAV al NSPanel que lo emite
            Los NSPanel Pro son los únicos puntos de captura y reproducción de audio.
            La laptop queda 100% desarrollo sin ningún servicio corriendo.
            Implementación: ver FASE 16 (Red de Nodos de Audio Multi-Ambiente).
            Esta tarea se completa al terminar FASE 16 Etapa A (16.1-16.4).

#### Etapa G — Workflow de deployment desde laptop

- [x] 21.22 Crear `scripts/deploy.sh` en el repo umbrella:
            ```bash
            #!/usr/bin/env zsh
            # Deploy home-agents al LXC de producción en el SER9.
            set -e
            ssh capitan "
              cd ~/workspace/home-agents &&
              git pull --recurse-submodules &&
              source ~/home-agents-env/bin/activate &&
              pip install -q -r core/requirements.txt &&
              systemctl --user restart capitan-core capitan-backoffice
            "
            echo "Deploy completo."
            ```
            Uso: `bash scripts/deploy.sh` desde la laptop tras mergear un PR a main.
- [x] 21.23 Actualizar `CLAUDE.md` del repo umbrella: reflejar nueva arquitectura, IP/hostname
            del LXC, comandos de deploy y de smoke test remoto.

#### Procedimientos de actualización (referencia operativa)

```zsh
# Ollama — en el LXC via SSH
ssh capitan "sudo systemctl stop ollama && curl -fsSL https://ollama.ai/install.sh | sh && sudo systemctl start ollama"
# Los modelos descargados sobreviven la actualización.

# HAOS — desde la UI del HAOS en la VM (192.168.68.101:8123)
# Settings → System → Updates → Check for updates / Install
# La VM de Proxmox no se toca.

# home-agents (core + backoffice)
bash scripts/deploy.sh   # desde la laptop, tras mergear PR a main

# ear — si está en el LXC del SER9
ssh capitan "cd ~/workspace/home-agents && git pull --recurse-submodules && systemctl --user restart capitan"

# ear — si está en la laptop (opción B de 21.21)
git -C ~/workspace/home-agents pull --recurse-submodules && systemctl --user restart capitan

# OS del LXC
ssh capitan "sudo apt update && sudo apt upgrade -y"

# Proxmox host — desde la UI de PVE o via SSH al host
ssh root@<ip-pve> "apt update && apt dist-upgrade -y"
```

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

### 2026-05-13
- Backoffice: página `/traces` unificada con solapas `proactive_check` / `goal_review`, listados flat ordenados por fecha descendente, paginados (25/página).
- Core: endpoint `/proactive/traces/{agent_id}` agrega `intent_type_counts` (conteo de items por tipo: advise/request/goal) para mostrarlo como badges en el listado sin leer el detalle.
- Templates `proactive_trace_list.html`, `proactive_trace_detail.html` y `traces.html` actualizados con badges de tipo.

### Pendiente decidir
- Latencia: ¿optimizar ahora o avanzar con la integración?
- Hardware servidor: timing y presupuesto

---

## ANEXO — ITERACIONES FUTURAS

Mejoras identificadas que no bloquean el plan actual pero vale la pena evaluar
en fases posteriores. Cada ítem tiene issue abierto en GitHub para seguimiento.

### A.1 Evaluar migración a Home Assistant MCP Server

**Contexto**: La integración actual con HAOS usa REST API con `entity_id` estáticos
en el contexto del LLM. El MCP Server de HA (`homeassistant.io/integrations/mcp_server`)
expone herramientas dinámicas (`list_entities`, `get_state`, `call_service`) que
permitirían al agente descubrir entidades en tiempo real y consultar estado antes de actuar.

**Por qué no ahora**: qwen2.5:7b vía Ollama no habla protocolo MCP nativamente.
Requeriría un puente MCP client → tool calls de Ollama, añadiendo complejidad sin
beneficio neto sobre lo que REST ya da.

**Condiciones para reevaluar**:
- Si Ollama incorpora soporte nativo MCP en alguna versión futura
- Si la lista de entidades crece lo suficiente como para que el contexto estático
  se vuelva un problema real
- Si se necesita leer estado antes de actuar (ej: "apagá lo que esté prendido")

**Restricción no negociable**: la solución debe correr 100% en LAN local, sin
tráfico a internet. Cualquier implementación MCP debe usar modelos locales (Ollama
u otro runtime local) como cliente MCP.

---

### ~~A.2 Red de nodos de audio multi-ambiente~~ → FASE 16

**Contexto**: La arquitectura actual tiene un único punto de acceso (la laptop con
micrófono y parlantes). Para hacer el agente realmente útil en toda la casa, se
necesitan nodos de audio en distintos ambientes (cocina, living, dormitorio, etc.)
que actúen como interfaces de voz distribuidas sobre la red WiFi hogareña.

**Hardware elegido: NSPanel Pro (Sonoff)**:
- Android 8.1 AOSP (Rockchip PX30 / RK3308), 64GB almacenamiento
- Micrófono y parlante accesibles desde Python via sounddevice/PortAudio (codec RK809)
- ADB over WiFi habilitado (puerto 5555), root disponible
- Termux instalado para scripts Python de voz; Termux:Boot para autoarranque
- HA Companion App como dashboard táctil (usuario HA por panel → dashboard por ambiente)
- Función dual: dashboard HA táctil + nodo de voz para home-agents
- Setup: ADB connect → instalar Termux → SSH → instalar Python + sounddevice + portaudio

**Arquitectura propuesta**:
- Nodos ligeros (NSPanel Pro o Raspberry Pi Zero 2W) con micrófono + parlante
- Cada nodo corre wake word detection localmente (openWakeWord, modelo capitan.onnx)
- Al detectar wake word, el nodo captura el audio del comando y lo envía via WebSocket
  o MQTT al servidor central (la laptop)
- El servidor central procesa STT → LLM → HAOS y devuelve el texto de respuesta al nodo
- El nodo sintetiza la respuesta con Piper TTS y la reproduce localmente
- Cada nodo se identifica con un nombre de ambiente (ej: `cocina`, `dormitorio`)
  para logs y ruteo de respuesta correcto

**Alternativa con hardware existente**:
- Los Echo (echo_de_matias, echo_dot, echo_pop_de_gala, echo_show) ya están en la casa
  y podrían usarse como parlantes de respuesta via HA `media_player.play_media`
- La captura de audio requeriría nodos propios de todas formas (los Echo son cerrados)

**Por qué no ahora**: requiere hardware adicional, diseño del protocolo de red
nodo↔servidor, y gestión de múltiples streams de audio simultáneos. La Fase 1 del
agente debe estar estable primero.

**Condiciones para reevaluar**:
- Cuando el agente single-node sea estable en uso diario
- Cuando haya presupuesto/tiempo para hardware de nodos
- Si el uso diario muestra que la cobertura de un solo ambiente es limitante

**Restricción no negociable**: todo el procesamiento pesado (STT, LLM, TTS) corre
en la laptop central. Los nodos son clientes ligeros — solo corren wake word detection
y streaming de audio. Nada sale de la LAN local.


### FASE 22 - Modelo de Intents Tipado (Intent Model 2.0)

```
Objetivo: Modelar correctamente los tres tipos de intents: advise (notificación TTL),
          request (el agente pide info al usuario; el siguiente mensaje ES la respuesta),
          goal (intención real cross-agente con árbol de sub-goals, ciclo de vida complejo
          y goal reviewer proactivo que busca cumplirlos con colaboración multi-agente).
Estado:   COMPLETA
Deps:     FASE 9 (intent_state básico), FASE 3.5 (WA para captura de request),
          FASE 12 (backoffice para vista de goals).
```

- [x] 22.1  **`core/intent_model.py`** — TypedDicts `AdviseIntent`, `RequestIntent`, `GoalIntent`,
            `GoalNote`. `VALID_TRANSITIONS` por tipo. `validate_transition()`, `is_active()`,
            `is_terminal()`. Sin dependencias — módulo puro de schema.

- [x] 22.2  **Refactorizar `core/intent_state.py`** — soporte de `intent_type` en `upsert()`,
            nuevos status (`active`, `acknowledged`, `succeeded`, `expired`). `acknowledge()`,
            `capture_reply()`, `get_pending_request()`. `_coerce_legacy()` para migración
            transparente sin script. Advise no genera recordatorios. Compat backward total.

- [x] 22.3  **`core/goal_store.py`** — storage separado en
            `~/.local/share/capitan/goals/{user_id}.json`. CRUD completo, árbol parent/child
            con cascade de completitud automático, `get_goals_for_agent()`, `get_goals_needing_review()`.

- [x] 22.4  **`_build_agent_prefix()` tipado** — advise `[AVISO]`, request `[PENDIENTE TU RESPUESTA]`,
            goals via `goal_store.get_goals_for_agent()` en sección separada. Filtra estados terminales.

- [x] 22.5  **Pipeline de captura de Request** en `process()` y `wa_inbound()` — el siguiente
            mensaje del usuario se captura sin pasar por el coordinador LLM. Hook opcional
            `handle_captured_reply()` en el agente origen.

- [x] 22.6  **`_apply_agent_updates()` tipado** — routea por `intent_type`. Soporte de `goal_updates`
            para transiciones explícitas de goals desde agentes.

- [x] 22.7  **`core/proactive.py` tipado** — `_persist_proactive_item()` routea por tipo.
            `_should_skip()` chequea `goal_store` para items tipo goal. WA notifications
            diferenciadas por tipo (question para request, detección de objetivo para goal).

- [x] 22.8  **Endpoints REST — Request capture** — `POST /users/{id}/intents/{id}/capture`,
            `GET /users/{id}/intents/pending-request`.

- [x] 22.9  **Endpoints REST — Goals** — CRUD completo + transition + notes + children.
            `GET /goals` (admin). Modelos Pydantic: `GoalCreate`, `GoalTransition`, `GoalNoteCreate`.

- [x] 22.10 **`core/base_agent.py` hooks opcionales** — `handle_captured_reply()`, `review_goal()`,
            `on_goal_transition()`. Duck-typed, sin herencia requerida.

- [x] 22.11 **Goal Reviewer en `ProactiveScheduler._loop()`** — `_review_goals()` itera goals
            activos vencidos por `review_interval_hours`. `discovered`→`planning` automático,
            `planning`/`in_progress` → llama `review_goal()` en colaboradores, `blocked` →
            reintenta o notifica. Hook opcional `review_goal(user_id, goal) -> {status?, note?}`.

- [x] 22.12 **Backoffice** — `intents.html` con badges de tipo, botón 'visto' para advise, form
            de captura para request, muestra `captured_reply`. `goals.html` nuevo: árbol,
            notas, colaboradores, transiciones. Sidebar con link Goals.

---

### FASE 23 - Routing LLM Genérico + Mejora Continua Bidireccional

```
Objetivo: Eliminar todo el keyword matching de los agentes. Reemplazarlo por routing
          LLM en dos niveles: coordinador elige agente (AgentCard) y cada agente elige
          su acción interna (BackendCard). Ambos niveles aprenden con cada interacción
          y mantienen un score de utilidad.
Estado:   COMPLETA
Deps:     FASE 9 (coordinator + FastClassifier), FASE 20 (ML), FASE 8 (CalendarAgent).
```

- [x] 23.1  **`core/backend_router.py`** — módulo nuevo. `BackendCard` dataclass con
            `action_id`, `label`, `description`, `requires_auth`, `auth_service`, `examples`.
            `to_catalog_text(extra_examples=None)` para enriquecer el catálogo con
            ejemplos aprendidos. `select_action(text, actions, model, auth_status,
            conv_context, agent_id)` — llama al LLM del agente con las BackendCards
            disponibles; filtra por `auth_status`; si solo hay una acción, retorna sin LLM;
            cuando se pasa `agent_id`, carga los ejemplos aprendidos de `agents.json` y los
            incluye en el catálogo.

- [x] 23.2  **`core/ml_agent.py` reescrito** — elimina todo keyword matching. Define
            `_ACTIONS: list[BackendCard]` con 5 acciones: `search_public`, `search_refine`
            (gated por contexto activo), `orders` (auth ml), `wishlist` (auth ml),
            `price_track` (gated). `process()` llama `select_action()` con `agent_id`.
            Fix incluido: `get_my_orders()` requiere `buyer={user_id}` en la API.

- [x] 23.3  **`core/mp_agent.py` reescrito** — elimina todo keyword matching. Define
            `_ACTIONS: list[BackendCard]` con 6 acciones: `balance`, `movements`,
            `pending_payments`, `summary`, `payment_link`, `request_money`.
            `process()` llama `select_action()` con `agent_id`.
            Flujo de confirmación (sí/no) se mantiene como máquina de estados antes del routing
            — es estado binario, no routing semántico.

- [x] 23.4  **`core/calendar_agent.py` — routing BackendCard** — define `_ACTIONS` con
            2 BackendCards: `holidays` (lookahead 365 días) y `calendar` (lookahead normal).
            `process()` llama `select_action()` con `agent_id` para determinar el lookahead
            en lugar del keyword matching anterior.

- [x] 23.5  **Mejora continua Nivel 1 — AgentCard** — `agent_config.append_learned_example()`
            + `agent_config.record_agent_outcome()`. `get_registry()` combina curados +
            `learned_examples` (deduplicados). FastClassifier se entrena con ejemplos combinados.
            `server.py` llama `record_agent_outcome()` con `success=not _is_error_result(resp)`
            después de cada request.

- [x] 23.6  **Mejora continua Nivel 2 — BackendCard** — `agent_config.record_action_outcome()`
            persiste en `action_examples.{action_id}`. `backend_router._load_action_examples()`
            los inyecta en el catálogo cuando se pasa `agent_id`. Cada agente llama
            `record_action_outcome()` con `success=desc is not None` después del dispatch.

- [x] 23.7  **Scoring de utilidad** — `agent_config.record_agent_outcome()` y
            `record_action_outcome()` actualizan contadores `{calls, successes}` en
            `agent_stats` y `action_stats[action_id]` respectivamente.
            `get_agent_stats(agent_id) → {calls, successes, score}` y
            `get_action_stats(agent_id) → {action_id: {calls, successes, score}}`.
            `score = successes/calls` con mínimo de 5 llamadas (None si < 5).
            Storage en `~/.local/share/capitan/agents.json`.

- [x] 23.8  **`backend_router.py` API unificada** — `record_agent_outcome(agent_id, text, success)`
            delega a `agent_config.record_agent_outcome()`. `record_action_outcome(agent_id,
            action_id, text, success)` delega a `agent_config.record_action_outcome()`.
            Las funciones anteriores `record_success` y `record_action_success` eliminadas.

---

### FASE 24 - Tracing Detallado de Interacciones

```
Objetivo: Guardar un trace completo de cada request — interacciones del coordinador con
          el LLM, catálogo de agentes analizado, agente seleccionado, acción del backend
          router, llamadas LLM del agente — y navegarlo en el backoffice para identificar
          oportunidades de mejora (ej: routing incorrecto, no-resultados evitables).
Estado:   COMPLETA
Deps:     FASE 9 (coordinator), FASE 23 (backend_router).
```

- [x] 24.1  **`core/trace_store.py`** — módulo nuevo. Dataclasses: `LLMCall` (source, model,
            system, prompt, raw_response, latency_ms, ts), `BackendRouterTrace` (catalog_text,
            action_selected, reason, llm_call), `AgentStepTrace` (agent_id, query,
            injected_prefix, backend_router, agent_llm_calls, response, success, latency_ms),
            `CoordinatorTrace` (input_text, catalog_text, fast_classifier_used, fast_agent,
            fast_conf, llm_call, plan_json, latency_ms), `RequestTrace` (trace_id, conv_id,
            ts, user_text, coordinator, steps, aggregation_call, final_response, total_latency_ms).
            Thread-local context: `set_current_trace(t)`, `get_current_trace()`, `add_llm_call(call)`.
            Storage: `~/.local/share/capitan/traces/{conv_id}.jsonl` (append-only, un JSON
            por línea). `append_trace(t)`, `get_traces(conv_id)` → lista reversed (más reciente
            primero), `get_trace(conv_id, trace_id)`. Retención: max 100 traces por conv_id.

- [x] 24.2  **Instrumentar `coordinator.py`** — `_call_llm()` retorna `(str, LLMCall|None)`.
            `coordinate()` captura: catalog_text, path tomado (fast_classifier o LLM),
            fast_agent/conf si aplica, y el plan resultante como JSON. `aggregate()` registra
            su llamada LLM como `aggregation_call` en el trace. Sin cambios en lógica ni firmas públicas.

- [x] 24.3  **Instrumentar `backend_router.py`** — `select_action()` captura catalog_text,
            system prompt, prompt enviado, respuesta raw del LLM, action seleccionada y reason.
            Persiste como `BackendRouterTrace` en el `AgentStepTrace` activo del trace actual.
            Si solo hay una acción (no se llama LLM), registra igual con `llm_call=None`.

- [x] 24.4  **Instrumentar `agent.py` (HAOS)** — `_ask_llm()` registra cada llamada LLM del
            agente HAOS en `agent_llm_calls` del step activo. Captura: model, system/prompt
            extraídos del messages[], raw_response, latency_ms.

- [x] 24.5  **Instrumentar `server.py`** — en `/process`: crea `RequestTrace`, lo activa como
            contexto thread-local, `_run_plan()` hace `push_step()` antes y `finish()` después
            de cada agente. Guarda trace en background al finalizar. `ProcessResponse` incluye
            `trace_id`.

- [x] 24.6  **REST endpoints en `core/server.py`** — `GET /conversations/{id}/traces` →
            lista de traces (summary: trace_id, ts, user_text, agents, latency, success).
            `GET /conversations/{id}/traces/{trace_id}` → trace completo como JSON.

- [x] 24.7  **Backoffice** — `trace_list.html`: lista de traces por conversación con badges.
            `trace_detail.html`: árbol visual expandible — Coordinador (fast-clf vs LLM, catálogo,
            plan), Steps (query, BackendRouter con catálogo + LLM call, llamadas LLM del agente,
            respuesta con highlight de errores), Agregación multi-step. Link "Traces" en
            `conversations.html`. Rutas `/conversations/{id}/traces` y `/{id}/traces/{trace_id}`.

### FASE 25 - Agente Google Maps

```
Objetivo: Agente de navegación y búsqueda de lugares usando Google Maps Platform.
          El usuario configura su propia API key; el agente resuelve rutas,
          búsquedas de lugares cercanos y detalles de establecimientos.
Estado:   COMPLETA
Deps:     FASE 9 (coordinador), FASE 3 (multi-agente), FASE 12 (backoffice para config de key).
API key:  GOOGLE_MAPS_API_KEY en core/.env — habilitadas: Geocoding, Places, Directions APIs.
```

- [x] 25.1  **`core/maps_client.py`** — wrapper HTTP sobre Google Maps Platform. Métodos:
            `geocode(address)` → (lat, lng); `reverse_geocode(lat, lng)` → dirección;
            `get_directions(origin, destination, mode)` → pasos, distancia_total, duracion_total;
            `search_nearby(location, place_type, radius_m)` → lista de places con name, rating,
            open_now, distance; `search_text(query, location)` → idem;
            `get_place_detail(place_id)` → name, address, phone, website, opening_hours, rating.
            API key desde `GOOGLE_MAPS_API_KEY` en `core/.env`.
            Lanza `MapsKeyMissing` si no está configurada, `MapsAPIError` para errores de la API.
            Cache de 10 min para geocoding y place details; sin cache para directions (tráfico en tiempo real).

- [x] 25.2  **Onboarding de API key** — si `GOOGLE_MAPS_API_KEY` falta o es inválida, el agente
            responde con instrucciones: URL de Google Cloud Console, APIs a habilitar (Geocoding,
            Places, Directions), cómo agregar la key al `core/.env`.
            En el backoffice: campo en `/settings` para ingresar `GOOGLE_MAPS_API_KEY`; botón
            "Verificar" hace una geocoding de prueba y muestra estado (válida / inválida / sin cuota).
            También configurable: `HOME_LOCATION` (dirección o lat,lng) usada como origen default.

- [x] 25.3  **`core/maps_agent.py`** — agente principal registrado en `agent_registry.py`.
            LLM extrae de la consulta: `intent` (directions / nearby_search / place_detail / geocode),
            `origin` (texto o "casa"), `destination`, `place_type` (restaurant, pharmacy, hospital…),
            `transport_mode` (driving/walking/transit; default driving), `location_ref` (texto libre).
            Si origin es "casa" o no se especifica, usa `HOME_LOCATION` del env.
            Descripción en el catálogo: keywords mapa, ruta, cómo llego, cómo voy, dónde queda,
            cerca, restaurante, farmacia, horario, abierto, google maps, direcciones.

- [x] 25.4  **Intent `directions`** — llama `get_directions()`. Respuesta para voz: distancia y
            tiempo total + 2-3 pasos clave en lenguaje natural ("Tomá Av. Italia y en 3km girá a
            la derecha en..."). Respuesta para WA/chat: tabla con todos los pasos, distancias
            parciales y duración parcial + deeplink `https://maps.google.com/maps?saddr=...&daddr=...`.
            Si `transport_mode=transit`, incluir líneas de transporte si la API las devuelve.

- [x] 25.5  **Intent `nearby_search` / `search_text`** — llama `search_nearby()` o `search_text()`.
            Lista top-5 con: nombre, rating (★★★☆☆), open_now (abierto/cerrado), distancia.
            Guarda resultados en `shared_state[source_key]["maps_results"]` para multi-turno:
            "el primero" / "más detalles del segundo" → llama `get_place_detail()` del ítem
            referenciado y responde con teléfono, web, horarios completos.

- [x] 25.6  **Intent `place_detail`** — cuando la consulta es directamente por un establecimiento
            ("¿a qué hora cierra el Farmashop de Pocitos?"). LLM extrae el nombre y posible
            zona; hace `search_text()` para resolver el place_id y luego `get_place_detail()`.
            Responde con horario del día actual resaltado, teléfono y estado abierto/cerrado ahora.

- [x] 25.7  **Registro definitivo y tests** — registrar en `agent_registry.py` con `id="maps"`,
            `description` orientada al coordinador LLM. Agregar `GOOGLE_MAPS_API_KEY` y
            `HOME_LOCATION` como vars opcionales al bloque `.env` en el backoffice y en `CLAUDE.md`.
            Tests manuales: ruta casa→trabajo, "farmacia cerca", "horario del McDonalds de 18 de julio".

---

### FASE 26 - Sistema de Rutinas

Estado: COMPLETA
Deps:   FASE 9 (coordinador + agent_history), FASE 22 (goal engine — modelo de referencia).

Las rutinas son patrones de comportamiento inferidos dinámicamente a partir del historial
de interacciones del usuario. A diferencia de los goals (intenciones explícitas), las rutinas
se detectan por observación y se construyen iterativamente.

- [x] 26.1  **`routine_store.py`** — persistencia en `~/.local/share/capitan/routines/{user_id}.json`.
            Máquina de estados: `candidate → active → paused | dismissed`.
            Promoción automática a `active` cuando `confidence ≥ 0.6` y `occurrence_count ≥ 3`.
            Deduplicación por similitud Jaccard antes de crear duplicados.
            API: `create_routine`, `record_occurrence` (EMA 30/70), `transition`, `find_similar`,
            `get_active_routines`, `mark_triggered`, `get_all_active_across_users`.

- [x] 26.2  **`routine_detector.py`** — detección LLM periódica.
            Carga mensajes del usuario de todos los agentes (solo role=user).
            Llama a qwen2.5:7b con prompt estructurado que pide JSON array de rutinas candidatas.
            Si detecta una rutina similar a una existente (Jaccard): incrementa ocurrencias.
            Si es nueva: crea `candidate`. Intervalo mínimo configurable (default 6h por usuario).
            `detect_for_user(user_id)` + `run_all_users()` para el poller de background.

- [x] 26.3  **Integración en `server.py`**:
            - Background thread `routine-detector` que llama `run_all_users()` cada 6h
              (configurable con `ROUTINE_DETECT_INTERVAL`).
            - `_build_agent_prefix()`: rutinas `active` inyectadas en el contexto de cada agente
              como `[RUTINA] Título (confianza: X%): descripción`.
            - `_apply_agent_updates()`: maneja `routine_updates` en el dict de retorno de agentes.
              Con `routine_id` → transiciona rutina existente.
              Sin `routine_id` + `title` → crea rutina candidata nueva.

- [x] 26.4  **Endpoints REST**:
            `GET /routines` — vista admin de rutinas activas de todos los usuarios.
            `GET /users/{uid}/routines[?status=...]` — rutinas de un usuario con filtro opcional.
            `POST /users/{uid}/routines` — crear rutina manualmente.
            `GET /users/{uid}/routines/{rid}` — detalle de una rutina.
            `POST /users/{uid}/routines/{rid}/transition` — transicionar estado.
            `DELETE /users/{uid}/routines/{rid}` — eliminar rutina.
            `POST /users/{uid}/routines/detect` — forzar detección inmediata (bloquea 60s máx).

- [x] 26.5  **`base_agent.py`**: documenta `routine_updates` en el contrato de retorno del protocolo.

---

### FASE 27 - Afinidades entre agentes + proactividad colaborativa

Estado: COMPLETA
Deps:   FASE 26 (SharedState), FASE 9 (proactividad base), FASE 24 (traces).

Los agentes pueden tener relaciones de afinidad configuradas por el usuario. Durante el ciclo
proactivo, cada agente construye automáticamente un contexto cross-dominio leyendo datos de
SharedState publicados por sus agentes afines. Esto habilita sugerencias proactivas que emergen
de la colaboración entre dominios sin hardcodear lógica inter-agente.

- [x] 27.1  **`shared_state.py`** — añade `get_by_prefix(prefix)`: retorna todas las entradas
            no expiradas cuya clave comienza con `prefix.`. Permite filtrar datos por namespace
            de agente (ej: `weather.*`, `calendar.*`) en O(n) sobre las entradas vivas.

- [x] 27.2  **`agent_config.py`** — cuatro funciones nuevas:
            `get/set_affinities(agent_id)` — lista de agent_ids con los que hay afinidad.
            `get/set_shared_state_prefix(agent_id)` — namespace que este agente publica en SharedState.
            Ambos persisten en `~/.local/share/capitan/agents.json`.

- [x] 27.3  **`proactive_mixin.py`** — `_build_affinity_context(agent_id)` lee affinities de
            agent_config, obtiene el shared_state_prefix de cada afín y llama get_by_prefix para
            construir un bloque de texto tipo "- weather (weather.*): temp=22.5, is_raining=False".
            En `proactive_check`: el bloque se inyecta al prompt del LLM entre active_intents y
            el historial. Hook `proactive_system_prompt`: si el agente define este atributo de clase,
            se usa como system prompt; si no, el genérico de ProactiveMixin.

- [x] 27.4  **`clima_agent.py`** — declara `shared_state_prefix = "weather"`. ClimaAgent ya
            publicaba `weather.*` en SharedState; ahora ese namespace queda formalizado para que
            otros agentes puedan declarar afinidad con él.

- [x] 27.5  **`maps_agent.py`** — hereda `ProactiveMixin` (primer agente no-genérico en hacerlo).
            `proactive_schedule = 3600` (horario). `default_affinities = ["weather"]` — por defecto
            tiene afinidad con el agente de clima. `proactive_system_prompt` orienta al LLM hacia
            sugerencias de movilidad emergentes del contexto (clima + rutinas + historial).

- [x] 27.6  **`core/server.py`** — `GET /agents` incluye `affinities` y `shared_state_prefix`
            por agente (con fallback a atributos de clase). Endpoints nuevos:
            `GET/PUT /agents/{id}/affinities` — leer/escribir lista de afines.
            `GET/PATCH /agents/{id}/shared-state-prefix` — leer/escribir namespace.

- [x] 27.7  **Backoffice** — `agent_edit.html` sección "Afinidades entre agentes":
            campo `shared_state_prefix` (qué namespace publica este agente) y multi-select
            de agentes afines con checkboxes, mostrando el namespace de cada uno.
            `backoffice/server.py` proxea los nuevos endpoints al core.

- [x] 27.8  **Tests** — `tests/test_agent_affinities.py`: 13 tests cubren get/set de affinities
            y shared_state_prefix, SharedState.get_by_prefix (incluye expiración y aislamiento
            de prefijos), y _build_affinity_context (sin affinities, con datos, sin prefix, sin datos).

---

### FASE 28 - Gestión de Modos por Canal (UX Multi-Canal)

```
Objetivo: Formalizar las capacidades de input/output de cada canal de interacción
          (wa, mic/ear, web) y hacer que el agente respete esas restricciones al
          elegir el modo de respuesta. Revisar el campo `notification_mode` del usuario
          para que tenga sentido en un contexto multi-canal.
Estado:   Pendiente
Deps:     FASE 3.5 (WA), FASE 18 (UX audio), FASE 12 (backoffice).
```

- [ ] 28.1  **Mapa de capacidades por canal** — definir en `core/` un diccionario o clase
            `CHANNEL_CAPS` que declare para cada canal (`"wa"`, `"ear"`, `"web"`) qué modos
            de input y output soporta:
            ```
            wa:  input=[text, audio], output=[text, audio]
            ear: input=[audio],       output=[audio]
            web: input=[text],        output=[text]
            ```
            El campo `source` que ya llega en `/process` se usa para lookupear las caps.
            Estas capacidades deben ser consultables desde el agente y desde el coordinador.

- [ ] 28.2  **Restricción de modo en el coordinador** — al construir el contexto de respuesta,
            el coordinador (o el dispatch en `agent_registry.py`) debe filtrar el modo elegido
            por el agente contra `CHANNEL_CAPS[source].output`. Si el agente pidió `audio` pero
            el canal es `web` (solo texto), degradar a `text` automáticamente y loguear el
            downgrade. Si el canal tiene múltiples opciones de output (ej. WA), respetar la
            elección del agente o la preferencia del usuario.

- [ ] 28.3  **Campo `response_mode` en la respuesta del agente** — el agente puede incluir en
            su respuesta un campo opcional `response_mode: "text" | "audio" | "auto"` para
            señalizar preferencia. `"auto"` (default) delega la decisión al canal/preferencia
            del usuario. El adaptador de cada canal (WA, ear, web) aplica la lógica:
            modo solicitado ∩ caps del canal, con fallback a text.

- [ ] 28.4  **Revisión de `notification_mode` del usuario** — el campo actual
            (`notification_mode: text | audio`) fue diseñado para WA pero su semántica es
            ambigua en multi-canal. Decidir e implementar una de estas opciones:
            a) Reemplazarlo por preferencias por canal: `channel_prefs.wa.output_mode`,
               `channel_prefs.ear.output_mode`, etc.
            b) Renombrarlo a `default_output_mode` y usarlo como fallback cuando el canal
               soporta múltiples modos y el agente devuelve `"auto"`.
            La opción (b) es más conservadora y suficiente hasta tener más canales activos.
            Actualizar backoffice (`user_edit.html`) para reflejar el campo renombrado/reestructurado.

---

### FASE 29 - Ejecución Real de Planes de Inversión

```
Objetivo: Pasar el agente de inversiones de modo "dummy" (P&L hipotética) a modo real:
          mapear un monto de capital a un plan, ejecutar las órdenes en un broker,
          y ofrecer palancas de entrada/salida manuales y automáticas.
Estado:   Pendiente
Deps:     FASE 6 (planes, portfolio.py, COMPLETA), FASE 9 (coordinador, COMPLETA),
          FASE 26 (rutinas, para triggers automáticos).
Nota:     Alcance inicial acotado a instrumentos con API pública disponible (crypto vía
          exchange API, CEDEARs/acciones vía broker con API REST). El modo dummy coexiste:
          los planes sin capital asignado siguen siendo hipotéticos.
```

- [ ] 29.1  **Abstracción de broker (`broker_client.py`)** — interfaz común para ejecutar
            órdenes de compra/venta independientemente del proveedor. Métodos:
            `place_order(ticker, side, amount_usd)`, `get_positions()`, `get_balance()`,
            `cancel_order(order_id)`. Primera implementación concreta: broker simulado
            (`SimulatedBroker`) que registra órdenes localmente sin tocar APIs externas,
            para poder desarrollar y testear el flujo completo antes de conectar un broker real.
            Diseño abierto para agregar `LemonBroker`, `IOLBroker`, `BitsoClient`, etc.

- [ ] 29.2  **Activación de plan con capital real (`portfolio.py`)** — `activate_plan(user_id,
            plan_name, capital_usd)`: marca el plan como "activo" con el capital asignado,
            calcula la cantidad de cada instrumento según los pesos del plan y el precio actual,
            y registra las órdenes de compra en `broker_client`. El plan activo tiene
            `mode: "real" | "simulated"` y `capital_usd`, `activated_at` en su metadata.
            Los planes sin activar conservan `mode: "dummy"` y su P&L hipotética.

- [ ] 29.3  **Seguimiento de posiciones reales** — `portfolio.py` distingue posiciones dummy
            (precio snapshot al crear el plan) de posiciones reales (cantidad efectiva comprada,
            precio promedio de entrada). `calculate_plan_pnl()` usa precios de broker para
            planes reales y yfinance para dummy. El backoffice muestra badge "REAL" / "DUMMY"
            por plan, y para planes reales muestra capital invertido, valor actual y P&L en $.

- [ ] 29.4  **Comandos de entrada/salida por voz y WA** — el agente de inversiones reconoce:
            - "activá el plan X con $Y" → `activate_plan()` + confirmación explícita antes de ejecutar
            - "salí del plan X" → liquida todas las posiciones del plan (`close_plan()`)
            - "salí de TICKER en el plan X" → cierra solo esa posición
            - "¿cómo están mis posiciones reales?" → resumen de planes activos con P&L en $
            Toda orden que mueve dinero real requiere confirmación del usuario antes de ejecutar
            (intent con `needs_reply: true` y texto "¿Confirmás la compra de X por $Y?").

- [ ] 29.5  **Palancas automáticas de entrada** — sistema de triggers configurables por plan:
            - `entry_trigger`: condición para auto-activar un plan (ej: "cuando BTC baje 5% en
              el día", "el primer lunes de cada mes"). Implementado como regla evaluada en
              `finance_alerts.check()` o como rutina de FASE 26.
            - `entry_capital_usd`: capital a invertir al dispararse el trigger.
            - Flujo: trigger evalúa → notifica al usuario con opción de confirmar o cancelar
              dentro de una ventana de tiempo (ej: 30min). Si no hay respuesta, no ejecuta.
            - Los triggers se configuran desde el backoffice (campo en el formulario del plan).

- [ ] 29.6  **Palancas automáticas de salida** — por posición o por plan completo:
            - `stop_loss_pct`: cierra automáticamente si P&L cae por debajo del umbral.
            - `take_profit_pct`: cierra si P&L supera el umbral.
            - `trailing_stop_pct`: stop dinámico que sigue el máximo alcanzado.
            - Evaluados en cada ciclo de `finance_alerts.check()`. Al dispararse, notifica
              por WA/TTS antes de ejecutar y da una ventana de cancelación configurable
              (`exit_confirm_window_sec`, default 0 = inmediato para stop_loss).
            - Configurables por plan desde el backoffice.

- [ ] 29.7  **Historial de órdenes reales** — `broker_client` persiste cada orden ejecutada
            en `finance_orders_{uid}.json`: timestamp, ticker, side, cantidad, precio, status,
            broker. Endpoint `GET /finance/plans/{uid}/orders` en core. Sección en backoffice
            bajo el plan activo: tabla de órdenes con filtro por plan y estado.

---

### FASE 30 - Tool Calling por Agente (Agentic Loop)

```
Objetivo: Reemplazar el patrón "prompt con acciones en texto + parse manual" por tool
          calling real sobre Ollama. Cada agente declara un conjunto de tools (opcionalmente
          vacío). El proceso de ejecución implementa un agentic loop: LLM decide qué tool
          invocar, el agente la ejecuta, el resultado vuelve al LLM, hasta que el LLM
          produce una respuesta final. Todo queda registrado en los traces.
          Las tools son administrables desde el backoffice y se hidratan a partir de
          schemas OpenAPI: generados automáticamente para el core-api, o a través de
          adapters para APIs externas.
Estado:   COMPLETA
Deps:     FASE 9 (coordinador), FASE 24 (tracing).
```

- [x] 30.1  **`ToolDef` y `ToolStore` (`tool_store.py`)** — modelo de datos para una tool y su
            store de persistencia por agente:
            - `ToolDef`: `name`, `description`, `parameters` (JSON Schema), `source_url`
              (de dónde se hidrataron), `last_refreshed_at`, `enabled: bool`.
            - `ToolStore`: CRUD de tools por `agent_id`, persistido en
              `~/.local/share/capitan/tools/{agent_id}.json`.
            - Las tools se pueden habilitar/deshabilitar individualmente sin eliminarlas.
            - Cada agente puede tener tools o no. Un agente sin tools sigue funcionando
              con su lógica actual como fallback.

- [x] 30.2  **Schema OpenAPI del core-api (`GET /openapi-tools`)** — endpoint en `server.py`
            que retorna un schema OpenAPI 3.0 de los endpoints internos de core que son
            candidatos a ser tools (subset explícitamente marcado, no toda la API).
            Los endpoints candidatos se anotan con un decorator o campo `expose_as_tool=True`.
            El schema incluye description, parameters y response summary para cada operación.
            Este endpoint es el que usan los agentes del sistema para auto-hidratarse.

- [x] 30.3  **Adapter OpenAPI para backends externos (`openapi_adapter.py`)** — módulo que,
            dado un backend con API documentada, produce un schema OpenAPI normalizado:
            - Si el backend expone `/openapi.json` o `/swagger.json`: lo consume directamente.
            - Si no: recibe un documento de descripción (markdown/texto) y lo convierte a
              schema OpenAPI mediante una llamada LLM (one-shot, resultado cacheado).
            Backends iniciales a cubrir: `trace_store` (interno, via 30.2), `intent_state`
            (interno, via 30.2), `weather_providers` (externo, Open-Meteo tiene OpenAPI),
            `ml_client` (externo, MercadoLibre tiene OpenAPI pública).
            El adapter expone `get_schema(backend_id) -> dict` que retorna el schema
            normalizado independientemente del origen.

- [x] 30.4  **Hidratación de tools por agente (`tool_hydrator.py`)** — lógica en el backend
            core que, dado un `agent_id`, obtiene el schema de cada backend asociado al agente
            (via 30.2 o 30.3), filtra las operaciones relevantes para ese agente, y actualiza
            el `ToolStore` con las `ToolDef` resultantes. Endpoint `POST /agents/{agent_id}/tools/refresh`
            que dispara la hidratación y retorna el listado actualizado. La lógica de "qué
            backend corresponde a qué agente" se declara en el agente mismo (`backends` ya
            existe en `base_agent.py`; extender con `tool_sources: list[str]`).

- [x] 30.5  **Agentic loop en `process()` (`agent_loop.py`)** — implementación genérica del
            loop de tool calling sobre Ollama (`/api/chat` con campo `tools`):
            ```
            messages = [system] + conv.context() + [user]
            while True:
                response = llm(messages, tools=enabled_tools)
                if response.stop_reason != "tool_use": break
                for call in response.tool_calls:
                    result = dispatch_tool(call.name, call.arguments)
                    messages.append(tool_result(call.id, result))
            return response.content
            ```
            `dispatch_tool` invoca el endpoint o función correspondiente a cada tool.
            El loop tiene un límite configurable de iteraciones (default 5) para evitar
            ciclos. Si se agota, el agente retorna la última respuesta parcial del LLM.
            Los agentes existentes migran a este loop cuando tienen tools habilitadas;
            sin tools, siguen con su lógica actual intacta.

- [x] 30.6  **`ToolCall` en traces (`trace_store.py`)** — agregar formalmente el evento de
            invocación de tool al modelo de trace:
            - Nueva dataclass `ToolCall`: `tool_name`, `arguments: dict`, `result: dict`,
              `latency_ms`, `ts`, `iteration: int` (número de vuelta del loop).
            - `AgentStepTrace` incorpora `tool_calls: list[ToolCall]`.
            - El agentic loop (30.5) registra cada `ToolCall` en el step activo via
              `record_tool_call()` (nuevo helper en `trace_store.py`).
            - Las `LLMCall` del loop se registran con `source = "agent_{agent_id}_iter_{n}"`.

- [x] 30.7  **Backoffice — gestión de tools por agente** — sección nueva en la página de
            configuración de cada agente en el backoffice:
            - Lista de tools disponibles con nombre, descripción, origen (URL del schema)
              y último refresh.
            - Toggle enable/disable por tool individual.
            - Botón "Refresh tools" que llama a `POST /agents/{agent_id}/tools/refresh`
              (30.4) y recarga la lista.
            - Si el agente no tiene `tool_sources` declarados, la sección muestra un
              mensaje informativo en lugar de un error.

- [x] 30.8  **Migración piloto: `SystemAgent`** — migrar `system_agent.py` como primer agente
            al nuevo modelo. Sus tools se hidratan desde el core-api (30.2): `list_agents`,
            `get_intents`, `list_proactive_runs`, `get_trace`, `get_goal`, etc. El `_SYSTEM`
            hardcodeado se reemplaza por un system prompt genérico sin lista de acciones.
            Los tests existentes se actualizan para cubrir el loop y la invocación de tools.

- [x] 30.9  **Tests** — `tests/test_tool_store.py`: CRUD de ToolDef, enable/disable, persistencia.
            `tests/test_tool_hydrator.py`: hidratación desde schema mockeado (sin llamadas
            reales). `tests/test_agent_loop.py`: loop completo con Ollama mockeado — verifica
            iteraciones, límite de ciclos, registro en trace.

---

### FASE 31 - Optimización de Performance LLM en SER9

```
Objetivo: Explorar palancas de mejora de latencia LLM en el SER9 (Beelink, Radeon 780M gfx1103).
          Baseline actual: 27.5s CPU-only, 13.3s ROCm con HSA_OVERRIDE_GFX_VERSION=11.0.0.
          Target: reducir latencia warm por debajo de 5s sin cambiar el modelo.
Estado:   Pendiente
Deps:     FASE 21 (SER9 operativo con LXC — COMPLETA)
Hardware: Beelink SER9 Pro — Ryzen AI 7 HX 255, 32GB DDR5, Radeon 780M (RDNA 3 / gfx1103)
```

- [x] 31.1  Vulkan backend: benchmarkar `OLLAMA_GPU_BACKEND=vulkan` vs ROCm en SER9.
            La 780M tiene soporte Vulkan nativo y estable — puede superar el ROCm parcial.
            Medir latencia warm con ambos backends. Documentar ganador en NOTAS.
- [x] 31.2  Warm LLM keepalive: configurar `OLLAMA_KEEP_ALIVE` para evitar descarga del
            modelo entre requests. Por defecto Ollama descarga el modelo tras 5 min idle.
            Agregar `OLLAMA_KEEP_ALIVE=-1` al systemd unit del LXC.
- [x] 31.3  Lazy entity index: diferir la construcción del entity index (nomic-embed-text)
            al primer request en lugar de hacerlo en startup. Elimina los 30s de arranque
            del core. El índice se construye en background al recibir el primer /process.
- [x] 31.4  Benchmark warm vs cold: medir latencia warm (modelo ya cargado) vs cold para
            entender el real bottleneck. Si warm < 3s, el problema es solo el cold start.
- [ ] 31.5  Quantización alternativa: benchmarkar qwen2.5:7b con distintas quantizaciones
            (q4_0 vs q4_k_m vs q5_k_m) en SER9 para encontrar el mejor balance velocidad/calidad.

---

### FASE 32 - Migración de datos a base de datos formal

```
Objetivo: Reemplazar los JSON files en ~/.local/share/capitan/ por una base de datos
          estructurada (SQLite). Elimina problemas de concurrencia, mejora queries,
          facilita backup y migración entre servidores.
Estado:   Pendiente
Deps:     FASE 21 (SER9 estable — COMPLETA)
Motivación: actualmente los datos (usuarios, intents, conversaciones, portfolios,
            contextos, routines, etc.) son ~30 archivos JSON sin esquema formal,
            sin transacciones, sin índices. Migración costosa pero necesaria para escalar.
```

- [ ] 32.1  Inventario y esquema: mapear todos los archivos JSON actuales a tablas SQLite.
            Identificar relaciones (user → intents, user → conversations, user → portfolio).
            Definir esquema con migraciones (alembic o schema_version manual).
- [ ] 32.2  Capa de acceso unificada: crear `core/db.py` con conexión SQLite y helpers
            CRUD que reemplacen los json read/write actuales. Mantener API idéntica
            para no romper agentes existentes.
- [ ] 32.3  Migración de datos existentes: script `scripts/migrate_to_db.py` que lee los
            JSON actuales y los inserta en la DB. Idempotente y con dry-run.
- [ ] 32.4  Migrar módulos críticos: users.py, conversations.py, intents.py, portfolios.
            Un módulo a la vez con tests. Los JSON se mantienen como fallback hasta
            que todos los módulos estén migrados.
- [x] 32.5  Backup automático: script diario que hace `sqlite3 capitan.db .dump > backup.sql`
            y lo guarda en un directorio de backups rotados (7 días).
- [ ] 32.6  Eliminar JSON files: una vez todos los módulos migrados y backup operativo,
            borrar los archivos JSON y el código de lectura legacy.
