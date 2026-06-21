# FASE 33 — Backoffice en la nube: diseño y contrato (Etapa A)

Documento de diseño de los ítems 33.1–33.4. Fuente de verdad del contrato entre el
Brain y la nube. Cualquier cambio de payload, comando o autenticación se refleja acá
**antes** de tocar código.

Plataforma: Google Cloud (Cloud Run + Firestore + Identity Platform + Secret Manager).

---

## 33.1 — Modelo egress-only y modelo de amenazas

### Principio rector

El Brain **sólo** abre conexiones salientes HTTPS hacia la nube. La nube nunca inicia
una conexión hacia la casa. No hay port-forwarding, no hay inbound, no hay túnel
persistente reverso administrado por terceros. Si la nube desaparece, la casa sigue
operando y el backoffice local (FASE 12, LAN) sigue disponible.

```
                 (1) push estado  ─────────────►
   [Brain LXC] ── (2) poll comandos ────────────►  [Cloud Run + Firestore] ◄── HTTPS ── [navegador]
                 (3) post resultado ───────────►
                          ▲
                  todas SALIENTES desde el Brain
```

Las tres interacciones del bridge (push estado, poll comandos, post resultado) son
requests HTTPS salientes iniciadas por el Brain. La nube responde dentro de esa misma
conexión; nunca abre una nueva hacia la LAN.

### Qué sale de la red local (dato que cruza a la nube)

- Estado de salud de servicios (up/down de core, LLM, ear, backoffice, WA).
- Latencias agregadas (STT / LLM / HAOS), promedios y por comando.
- Lista de agentes activos y su estado on/off.
- Últimos N comandos de voz: texto del comando, agente que respondió, latencia,
  timestamp. **Texto del comando incluido** — asumido de bajo riesgo (domótica),
  pero ver "datos a minimizar".
- Métricas de wake word (score, falsos positivos, estado del nodo).
- Usuarios: sólo `id`, `nombre`, `rol`, conteos. **Sin** documentos, sin PII de
  contacto, sin tokens de servicios.
- Resultado de comandos admin ejecutados (stdout acotado / código de salida).

### Qué NO sale NUNCA de la red local

- `HAOS_TOKEN` y cualquier credencial en `core/.env` / `backoffice/.env`.
- Tokens OAuth de servicios de usuario (Google, MercadoLibre, etc.).
- Documentos de usuario / PII sensible (DNI, expiraciones, datos de contacto).
- El `.env` de ningún submodule, claves SSH, ni secretos de despliegue.
- Direcciones IP internas y topología detallada de la LAN más allá de lo necesario
  para dibujar el dashboard.
- Audio crudo, embeddings de voz, ni samples de wake word.

Regla de minimización: el bridge construye el snapshot a partir de un **subconjunto
explícito allow-list** de campos. Nunca serializa objetos de dominio completos. Si un
campo no está en el contrato de 33.2, no se envía.

### Por qué la nube no puede iniciar conexiones hacia la casa

- No existe ningún endpoint inbound en el Brain expuesto a internet. El LXC no tiene
  puerto publicado ni regla de NAT/port-forward en el router.
- La nube no conoce ninguna IP pública enrutable hacia la casa (IP dinámica + sin
  DNS dinámico apuntando al Brain).
- El control fluye por inversión: la nube **encola** comandos en Firestore; el Brain
  los **busca** (pull) en su próximo ciclo de polling. La nube nunca "empuja" al Brain.
- Aunque la cuenta de nube se comprometa, el atacante sólo puede encolar comandos del
  catálogo tipado (33.3), que se ejecutan con permiso mínimo y quedan auditados. No
  obtiene shell, ni los secretos, ni acceso a HAOS.

### Modelo de amenazas (resumen)

| Amenaza | Mitigación |
|---|---|
| Compromiso de la cuenta/proyecto GCP | Comandos sólo del catálogo tipado; sin shell arbitrario; secretos nunca en la nube; auditoría de cada comando. |
| Interceptación en tránsito | HTTPS gestionado por Cloud Run; verificación de firma del payload (33.14). |
| Replay de un comando | `id` único + estado `done` idempotente; TTL en la cola; rechazo de comandos ya ejecutados. |
| Acceso no autorizado al dashboard | Identity Platform con allow-list por email (33.8); sin registro abierto. |
| Robo de credencial del bridge | Service Account de permiso mínimo, token OIDC de corta vida, rotación documentada (33.13). |
| Caída de la nube | Failover: la casa sigue local; bridge reintenta con backoff (33.17). |
| Exfiltración de PII vía snapshot | Allow-list de campos; PII y tokens excluidos por diseño (este doc). |

---

## 33.2 — Contrato del snapshot de estado (Brain → nube)

Endpoint destino: `POST /ingest/state`. El bridge envía el snapshot completo en cada
ciclo (idempotente: la nube reemplaza el snapshot actual y conserva histórico corto).

### Esquema (JSON)

```jsonc
{
  "schema_version": 1,
  "ts": "2026-06-16T12:00:00Z",        // ISO-8601 UTC, momento de captura
  "host": "capitan-lxc",                // identificador del emisor (no IP)
  "services": {                          // up/down por servicio
    "core":       { "up": true,  "detail": "ok" },
    "llm":        { "up": true,  "detail": "qwen2.5:7b warm" },
    "ear":        { "up": true,  "detail": "2 nodos" },
    "backoffice": { "up": true,  "detail": "ok" },
    "wa":         { "up": false, "detail": "stopped" }
  },
  "latency": {                           // milisegundos, promedios móviles
    "stt_ms":  4600,
    "llm_ms":  3500,
    "haos_ms": 120,
    "by_command": [                      // últimas mediciones por comando (acotado)
      { "cmd": "prende la luz", "stt_ms": 4500, "llm_ms": 3200, "haos_ms": 110 }
    ]
  },
  "agents": [                            // agentes y su estado
    { "id": "haos",    "active": true,  "proactive": false },
    { "id": "clima",   "active": true,  "proactive": true  },
    { "id": "finance", "active": false, "proactive": false }
  ],
  "recent_commands": [                   // últimos N (default 20), sin PII
    {
      "ts": "2026-06-16T11:58:30Z",
      "text": "prende la luz del comedor",
      "agent": "haos",
      "ok": true,
      "latency_ms": 7800
    }
  ],
  "wakeword": {
    "last_score": 0.83,
    "false_positives_24h": 1,
    "nodes": [
      { "id": "comedor", "ip": "192.168.68.113", "online": true, "rms": 1000 }
    ]
  },
  "users_summary": [                     // sin documentos, sin tokens, sin PII
    { "id": "matias", "name": "Matías", "role": "admin", "intents_pending": 2 }
  ]
}
```

### Reglas del contrato

- `schema_version` obligatorio. La nube rechaza versiones que no entiende (no degrada
  en silencio).
- Tamaño acotado: `recent_commands` y `latency.by_command` con tope (default 20) para
  mantener el payload chico y dentro del free tier.
- Listas allow-list: cada objeto incluye **sólo** los campos del esquema. El bridge no
  reenvía objetos de dominio completos.
- `ip` de nodos se incluye sólo para mostrar topología en el dashboard; es IP privada
  (LAN), no enrutable. Evaluar omitirla si no aporta.
- Sin tokens, sin documentos, sin audio, sin embeddings (ver 33.1).
- La nube sella el snapshot con su propio `received_at`; no confía en el `ts` del
  emisor para ordenar histórico.

---

## 33.3 — Catálogo tipado de comandos admin (allow-list)

Principio: **NUNCA shell arbitrario.** Cada comando es un tipo cerrado con `type`
fijo y parámetros validados contra un esquema. El executor (33.12) mapea cada `type`
a una función concreta; un `type` desconocido se rechaza sin ejecutar.

### Estructura de un comando (en la cola Firestore)

```jsonc
{
  "id": "cmd_01HXYZ...",                // generado por la nube, único
  "type": "service.restart",            // del catálogo cerrado de abajo
  "params": { "service": "capitan-core" },
  "issued_by": "matias@blasi.ar",       // email autenticado que lo emitió
  "issued_at": "2026-06-16T12:01:00Z",
  "status": "pending",                  // pending | running | done | error
  "result": null,                       // se completa al postear resultado
  "ttl_at": "2026-06-17T12:01:00Z"      // expiración en Firestore
}
```

### Catálogo (v1)

| `type` | Parámetros | Validación | Acción en el Brain |
|---|---|---|---|
| `service.restart` | `service` ∈ {`capitan-core`, `capitan-backoffice`, `capitan-wa`, `capitan-ear`} | enum cerrado | `systemctl --user restart <service>` |
| `service.status` | `service` (mismo enum) o vacío = todos | enum/opcional | `systemctl --user status` parseado |
| `deploy.run` | `restart_wa`: bool | bool | ejecuta `scripts/deploy.sh` |
| `logs.tail` | `service` (enum), `lines`: int 1..500 | enum + rango | `journalctl --user -u <service> -n <lines>` |
| `config.reload` | `target` ∈ {`core`, `backoffice`} | enum | recarga config sin redeploy |
| `wakeword.retrain` | — | — | dispara `/wakeword/train` (FASE async) |
| `voice.reenroll` | `node_id`, `user_id` | existen en estado | re-enrola embedding desde el nodo |

Notas:
- Cada `type` es exhaustivo: parámetros fuera del esquema → rechazo, no ejecución.
- Los enums se validan contra el estado conocido (servicios/nodos/usuarios reales),
  no contra texto libre.
- Comandos de larga duración (`deploy.run`, `wakeword.retrain`) pasan a `running` y
  reportan resultado al terminar; el dashboard muestra el progreso.
- El catálogo es versionado junto al executor. Agregar un comando = agregar el tipo
  acá **y** la función concreta en el executor; nunca uno sin el otro.

---

## 33.4 — Autenticación bidireccional

### Dashboard (navegador → nube)

- **Identity Platform / Firebase Auth.** Login con proveedor (Google) restringido por
  **allow-list de email** (33.8): sólo `matias@blasi.ar` (y los que se agreguen
  explícitamente). Sin auto-registro.
- El frontend obtiene un ID token de Firebase; cada request a la API de Cloud Run lo
  envía en `Authorization: Bearer`. Cloud Run valida el token y el claim de email
  contra la allow-list antes de servir datos o aceptar emisión de comandos.
- Reglas de seguridad de Firestore por colección (33.6) refuerzan el acceso del lado
  de datos: lectura del dashboard sólo para emails autorizados.

### Bridge (Brain → nube)

- El bridge se autentica con un **token OIDC de Service Account** (sin API key
  embebida en el repo). La SA tiene permiso mínimo: invocar el servicio Cloud Run de
  ingest/commands, nada más.
- Token de corta vida obtenido del metadata/credenciales de la SA; el bridge lo
  refresca automáticamente. Cloud Run valida el `aud` y la identidad de la SA.
- La clave de la SA (si se usa archivo, no Workload Identity) vive **fuera del repo**,
  en el filesystem del LXC con permisos restrictivos, referenciada por env var. En la
  nube los secretos van en Secret Manager.

### Integridad de payload

- Además del transporte TLS, el snapshot y los resultados de comando se firman
  (HMAC con secreto compartido del bridge, o la propia identidad OIDC) y la nube
  verifica antes de aceptar (33.14). Esto evita que un cliente sin la credencial del
  bridge inyecte estado falso aunque conozca la URL.

### Rotación de credenciales

- Secreto/clave de la SA del bridge: rotación documentada (33.13). Procedimiento:
  generar nueva credencial en GCP → cargar en Secret Manager / filesystem del LXC →
  reiniciar el bridge → revocar la anterior. Sin downtime del sistema local.
- HMAC compartido (si se usa): rotación con ventana de doble-aceptación (acepta clave
  vieja y nueva durante la transición) para no perder snapshots.
- Allow-list de emails del dashboard: gestionada en config de Identity Platform,
  cambio inmediato sin redeploy.

---

## Decisiones de Etapa A (no reabrir sin justificación)

- Control por **inversión / pull**: la nube encola, el Brain polea. Cero inbound.
- Firestore unifica **estado + cola de comandos** (vs Pub/Sub) para tener histórico
  y auditoría con TTL en un solo lugar.
- Comandos **tipados y cerrados**, nunca shell. Catálogo versionado junto al executor.
- Secretos y PII **nunca** cruzan a la nube. Snapshot por allow-list de campos.
- Auth dashboard por Identity Platform + allow-list de email; bridge por OIDC de SA.
