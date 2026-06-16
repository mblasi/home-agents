# cloud/ — Backoffice en la nube (FASE 33)

Backoffice accesible desde internet **sin exponer el SER9 ni HAOS**. La nube nunca
inicia conexiones hacia la casa: el SER9 empuja estado y polea una cola de comandos
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

Bridge (SER9 → nube, auth OIDC de la SA del bridge):
- `POST /ingest/state` — recibe el snapshot.
- `GET  /commands/pending` — devuelve pending y los pasa a running (claim atómico).
- `POST /commands/{id}/result` — resultado de ejecución.

Dashboard (navegador → nube, auth Firebase + allow-list email):
- `GET  /api/state` · `GET /api/commands` · `GET /api/catalog`
- `POST /api/commands` — emite un comando validado contra el catálogo.
- `GET  /` — dashboard.

## Provisión / deploy

```bash
PROJECT=capitan-495518 REGION=southamerica-east1 \
  ALLOWED_EMAILS=matias@blasi.ar bash infra/provision.sh
```

Login del dashboard (Firebase Auth + Google sign-in), automatizado:

```bash
PROJECT=capitan-495518 REGION=southamerica-east1 bash infra/setup_firebase.sh
```

`setup_firebase.sh` hace: addFirebase → crea la web app → habilita el proveedor Google
(OAuth Google-managed, sin client manual) → agrega el dominio de Cloud Run a
*authorized domains* → fija `FIREBASE_API_KEY`/`FIREBASE_AUTH_DOMAIN` en el servicio.
Idempotente. El acceso queda restringido por `ALLOWED_EMAILS` (validado en el backend).

## Variables de entorno del servicio

| Var | Uso |
|---|---|
| `GCP_PROJECT` | proyecto (Firestore + verificación de tokens) |
| `FIREBASE_PROJECT_ID` | audiencia del Firebase ID token (= proyecto) |
| `ALLOWED_EMAILS` | allow-list de login (coma-separada) |
| `BRIDGE_SA_EMAIL` | email de la SA del bridge autorizada a ingest/commands |
| `SERVICE_URL` | audiencia esperada del OIDC del bridge |
| `FIREBASE_API_KEY` / `FIREBASE_AUTH_DOMAIN` | config web de Firebase Auth |

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
