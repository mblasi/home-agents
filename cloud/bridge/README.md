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
