# cloud/ — Backoffice en la nube (FASE 33)

Backoffice accesible desde internet **sin exponer el Brain ni HAOS**. La nube nunca
inicia conexiones hacia la casa: el Brain empuja estado y polea una cola de comandos
(patrón command/executor, control por inversión). Toda conexión es SALIENTE desde la
LAN. Diseño/contrato: `../masterplan/fase33_cloud_backoffice.md`.

## Stack

- **Cloud Run** (FastAPI, scale-to-zero) — web + API.
- **Firestore** (native) — snapshot de estado + cola de comandos, con TTL.
- **Identity Platform / Firebase Auth** — login del dashboard, allow-list por email.
- **Secret Manager** — credenciales.
- **Service Accounts** — runtime (`datastore.user`) y bridge (sin roles, sólo OIDC).

## Estructura

```
cloud/
├── app/
│   ├── main.py          FastAPI: ingest/commands (bridge) + API/dashboard (browser)
│   ├── auth.py          Firebase ID token (dashboard) + OIDC SA (bridge)
│   ├── firestore_db.py  estado + cola de comandos
│   ├── models.py        contrato del snapshot/comando (Pydantic)
│   ├── commands.py      catálogo TIPADO de comandos (allow-list, sin shell)
│   ├── templates/       dashboard.html
│   └── static/          style.css
├── tests/               tests del catálogo
├── Dockerfile
├── requirements.txt
├── firestore.rules      deny-all de cliente (defense in depth)
└── infra/provision.sh   IaC idempotente (gcloud)
```

## Endpoints

Bridge (Brain → nube, auth OIDC de la SA del bridge):
- `POST /ingest/state` — recibe el snapshot.
- `GET  /commands/pending` — devuelve pending y los pasa a running (claim atómico).
- `POST /commands/{id}/result` — resultado de ejecución.

Dashboard (navegador → nube, auth Firebase + allow-list email):
- `GET  /api/state` · `GET /api/commands` · `GET /api/catalog` · `GET /api/me`
- `GET  /api/alerts` (access) · `GET /api/logs` (emit, poll del último logs.tail/satellite)
- `POST /api/commands` — emite un comando validado contra el catálogo.
- `GET  /` — dashboard SPA (sidebar + secciones, mobile-first; FASE 37).

El frontend es un **SPA con sidebar** (Monitoreo / Sistema / Administración), router por hash y
secciones gated por capacidad (`access`/`view_full`/`view_pii`/`emit`). La UI de comandos es
final-user: acciones contextuales por entidad + formularios tipados desde `/api/catalog` (sin JSON
crudo). `/api/catalog` enriquece cada parámetro con metadata de presentación
(`kind`/`label`/`choices`/`min`/`max`/`default`) sin tocar `validate_command`.

## Deploy de servicios (FASE 34)

El dashboard incluye una **matriz de targets**: una fila por componente que corre (core,
audio_server, backoffice, cloud-bo, un satélite por panel) con la versión que corre, la última
disponible y un botón "Actualizar" (rol admin). El botón emite el comando que el bridge del
Brain polea y ejecuta con el motor único (`cloud/bridge/deploy_engine.py`): `deploy.release`
(services del Brain), `deploy.cloud` (cloud-bo en GCP), `deploy.satellites` (force pull de un
panel). Health-gate + rollback automático; logs en vivo en el dashboard. Detalle del motor en
`cloud/bridge/README.md`.

El **deploy del propio cloud-bo** lo dispara el Brain (`gcloud run deploy --source` desde el
LXC, egress a Google) — NO pasa por el bridge (evita la circularidad de reiniciarse a sí mismo,
D4); si rompe, el rollback a la revisión previa lo hace el Brain.

## Provisión / deploy

```bash
PROJECT=capitan-495518 REGION=southamerica-east1 \
  ALLOWED_EMAILS=matias@blasi.ar bash infra/provision.sh
```

Login del dashboard (Firebase Auth + Google sign-in):

**Prerrequisito manual** (Identity Platform exige un OAuth client propio): en la consola
crear el OAuth consent screen y un **OAuth client ID (Web)** con redirect
`https://<project>.firebaseapp.com/__/auth/handler`. Copiar client id y secret.

```bash
PROJECT=capitan-495518 REGION=southamerica-east1 \
  GOOGLE_CLIENT_ID=...apps.googleusercontent.com \
  GOOGLE_CLIENT_SECRET=GOCSPX-... \
  bash infra/setup_firebase.sh
```

`setup_firebase.sh` hace: addFirebase → web app → `initializeAuth` → habilita el proveedor
Google con el client → agrega el dominio de Cloud Run a *authorized domains* → fija
`FIREBASE_API_KEY`/`FIREBASE_AUTH_DOMAIN` en el servicio. Idempotente. El acceso queda
restringido por `ALLOWED_EMAILS` (validado en el backend).

## Variables de entorno del servicio

| Var | Uso |
|---|---|
| `GCP_PROJECT` | proyecto (Firestore + verificación de tokens) |
| `FIREBASE_PROJECT_ID` | audiencia del Firebase ID token (= proyecto) |
| `ALLOWED_EMAILS` | allow-list de login (coma-separada) |
| `BRIDGE_SA_EMAIL` | email de la SA del bridge autorizada a ingest/commands |
| `SERVICE_URL` | audiencia esperada del OIDC del bridge |
| `FIREBASE_API_KEY` / `FIREBASE_AUTH_DOMAIN` | config web de Firebase Auth |
| `SSO_SECRET` | secreto HMAC compartido con el backoffice local (firma el token SSO) |
| `LOCAL_SSO_ORIGINS` | allow-list de orígenes LAN del backoffice local para el redirect SSO |

## SSO con el backoffice local (33.22–33.24)

El backoffice local (LAN, `:8080`) reusa este login en vez de un token compartido. La nube
actúa de broker: `/sso/start?redirect_uri=<local>/sso/callback` hace el Google sign-in y
`/sso/mint` emite un token HMAC firmado (exp corto) que redirige al backoffice local, el cual
lo verifica, resuelve email→usuario→rol contra su DB y abre sesión con RBAC (admin escribe;
familiar/adolescente read-only). El `redirect_uri` se valida contra `LOCAL_SSO_ORIGINS`. El
codec del token está espejado en `cloud/app/sso.py` y en el backoffice.

## Contrato del snapshot — qué sale y qué NO (FASE 37.1)

El `StateSnapshot` (`app/models.py`) es una **allow-list cerrada**: sólo viaja lo enumerado.
Campos ampliados en FASE 37 y su gate RBAC:

| Campo | Contenido | Gate | PII |
|-------|-----------|------|-----|
| `alerts` | textos de alertas proactivas (listas para TTS) | `access` | no secreta — son avisos del hogar, no contenido de conversaciones |
| `wakeword.status` | estado del último retrain (idle/running/done/error) | `access` | no |
| `counts.{intents,goals,routines,conversations}` | **sólo enteros** | `access` | no — el contenido nunca sale |
| `versions` | matriz de targets desplegables (FASE 34) | `access`/`emit` | no |

**Nunca sale de la LAN**: `.env`, tokens HAOS/OAuth, ni el **contenido** de intents, goals,
rutinas o conversaciones (sólo su conteo). El detalle PII queda detrás de la capacidad
`view_pii` (admin-only, 37.2), que **no** se sirve por este snapshot — se obtiene por
comando-poll explícito. El tipo de `counts` son enteros: es imposible filtrar texto por ahí.

## Seguridad

- Secretos y PII **nunca** cruzan a la nube (ver contrato 33.1/33.2).
- Comandos **tipados y cerrados**; un tipo fuera del catálogo se rechaza sin ejecutar.
- Reglas Firestore deny-all de cliente: el dashboard sólo accede vía la API server-side.
- Bridge SA sin roles de proyecto: sólo su identidad OIDC; permiso mínimo absoluto.

## Seguridad, costo y operación (Etapa D)

- **Rate limiting** (33.14): token bucket in-memory por identidad — ingest/pending 120/min,
  emisión de comandos 60/min (`app/ratelimit.py`). Middleware `BodySizeLimit` rechaza
  payloads > 512 KB con 413. La firma/verificación es el propio ID token OIDC (Google-signed);
  los payloads se validan con Pydantic.
- **Auditoría** (33.15): el dashboard muestra cada comando con estado, tipo, params, quién lo
  emitió, cuándo y el resultado (ok/output o error).
- **Costo / free tier** (33.16): Cloud Run `min-instances=0` (scale-to-zero), Firestore native
  con TTL para acotar almacenamiento. Budget de USD 5 con alertas a 50/90/100% del billing.
- **Failover** (33.17): si la nube cae, el `core` ni se entera (el bridge es un proceso
  aparte); el bridge reintenta con backoff exponencial (10→300s) y se recupera solo. Si el
  bridge cae, el backoffice local en LAN (`:8080`, FASE 12) sigue operando. Verificado e2e.
