# cloud/bridge/ — Bridge/executor del Brain (FASE 33 Etapa C)

Daemon que corre en el LXC del Brain (no en la nube). Hace **sólo conexiones
salientes** hacia el servicio Cloud Run (`cloud/`):

- `cloud_bridge.py` — loop: push del snapshot (`/ingest/state`) cada `PUSH_INTERVAL`
  y poll de comandos (`/commands/pending`) cada `POLL_INTERVAL`, con backoff.
- `snapshot.py` — arma el snapshot reusando core (:8765) + audio_server (:8766) +
  `/tmp/capitan`. Allow-list de campos; nunca tokens/PII.
- `executor.py` — ejecuta cada comando del catálogo TIPADO con una función concreta
  (subprocess con lista de args, sin shell). El catálogo es el mismo de la nube
  (`cloud/app/commands.py`), re-validado en el bridge.
- `deploy_engine.py` — el **motor de deploy** (FASE 34): único backend para todo deploy.
- `deploy_cli.py` — invocador LOCAL por target: resuelve `<target>` al mismo comando tipado que
  el cloud-bo y lo corre con `validate_command` + `executor.execute` (lo llama `scripts/deploy.sh`).

## Motor de deploy (FASE 34)

`deploy_engine.py` es el ÚNICO lugar con lógica de deploy (snapshot → pin de ref → install →
restart → health-gate → rollback → registro de versión). Lo invocan dos disparadores que
convergen en el MISMO funnel `validate_command` + `executor.execute`:
- **remoto** — el cloud-bo encola un comando → el bridge lo polea → `executor.execute`.
- **local** — `scripts/deploy.sh <target>` → `deploy_cli.py` resuelve el target al mismo comando
  → `executor.execute`. Desplegar desde la LAN (Claude) es idéntico a hacerlo desde el cloud-bo.

Modelo en tres capas:
- **Repo** (unidad de versión): `core`, `ear`, `umbrella`. Pin independiente por repo con
  `git checkout` (NO `git submodule update`): pinar el umbrella no pisa core/ear.
- **Service** (unidad de restart/health): `core`, `ear`(audio_server), `backoffice`, `wa`,
  `bridge`. Atomicidad POR-REPO (D7): si un service falla su health, se revierte SU repo.
- **Target** (unidad de operación, 34.15): lo que se ve y se opera en la matriz. Registro
  `TARGETS` (core, audio_server, backoffice, cloud-bo, + un satélite por panel). Cada target
  mapea a un comando: services → `deploy.release`, cloud-bo → `deploy.cloud`, paneles →
  `deploy.satellites`. El snapshot (`snapshot._versions`) produce `versions.targets` con la
  versión que corre + la última disponible + `behind` + el comando que lo despliega; ambos
  frontends sólo renderizan y emiten.

Comandos de deploy (catálogo tipado, validados en nube y bridge):
- `deploy.release {services?, core_ref?, ear_ref?, umbrella_ref?}` — services del Brain; sin
  params = todo a HEAD de main; `*_ref` pinea cada repo a un tag/sha.
- `deploy.cloud {services?}` — targets de Cloud Run (cloud-bo). Build `gcloud run deploy
  --source` desde el Brain (egress a Google) + `--to-latest`; health-gate por curl; rollback
  a la revisión previa (`update-traffic --to-revisions`). Registra el sha de umbrella que corre.
- `deploy.satellites {node_id?}` — fuerza el pull de código de un panel (o todos con `*`/ausente):
  marca el nodo en el audio_server (`POST /nodes/{id}/update`); su próximo heartbeat devuelve
  `update:true` y el satélite corre `_check_code_update()` fuera del ciclo de 10 min.

Versionado: tras un deploy sano, tag semver por repo (gate `DEPLOY_TAG_RELEASES`). Estado
persistido en `~/.local/share/capitan/deploy_state.json` (matriz de versiones + último release).

## Credencial (33.13)

La SA del bridge (`capitan-bridge@<project>.iam.gserviceaccount.com`) **no tiene
roles de proyecto**: sólo se usa su identidad para mintear ID tokens OIDC con
audience = URL del servicio. La key vive **fuera del repo**, en el LXC:

```
~/.config/capitan/bridge-sa-key.json   # chmod 600, gitignored
```

Rotación: generar nueva key (`gcloud iam service-accounts keys create`), reemplazar
el archivo, `systemctl --user restart capitan-bridge`, y borrar la key vieja
(`gcloud iam service-accounts keys delete`).

## Config (`~/.config/capitan/bridge.env`)

```
CLOUD_URL=https://capitan-cloud-m2x3ep3hfa-rj.a.run.app
BRIDGE_SA_KEY=%h/.config/capitan/bridge-sa-key.json
CORE_URL=http://localhost:8765
AUDIO_SERVER_URL=http://localhost:8766
PUSH_INTERVAL=30
POLL_INTERVAL=10
```

## Instalación en el LXC

```bash
cp cloud/bridge/capitan-bridge.service ~/.config/systemd/user/
~/home-agents-env/bin/pip install -r cloud/bridge/requirements.txt
systemctl --user daemon-reload
systemctl --user enable --now capitan-bridge
journalctl --user -u capitan-bridge -f
```
