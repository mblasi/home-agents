Desplegá home-agents al Brain (LXC de producción, brain-ai 192.168.68.132) por TARGET.

`scripts/deploy.sh <target>` resuelve el target al MISMO comando tipado que emite el cloud-bo
(deploy.release / deploy.cloud / deploy.satellites) y lo corre con validate_command +
executor.execute en el Brain — el mismo funnel que el bridge usa al desencolar un comando de la
nube. Desplegar desde acá es idéntico a hacerlo desde el cloud-bo. El motor hace pin a HEAD de
main, install, restart, health-gate y rollback automático si el health falla.

Targets (mismos que la matriz del cloud-bo):
- `core` `audio_server` `backoffice` `wa` `bridge` — services del Brain (deploy.release)
- `cloud-bo` — Cloud Run en GCP (deploy.cloud; activa la SA de deploy)
- `panels` o un `<node_id>` (ej. `nspanel-comedor`) — fuerza el pull del satélite (deploy.satellites)
- sin target — services default (core + ear + backoffice) a HEAD de main
- `--ref repo=ref` — pin a un tag/sha (rollback o release fijo), ej. `--ref core=v0.1.0`
- `--restart-wa` — compat: services default + wa

Prerrequisito: el cambio ya tiene que estar mergeado a main (el motor pinea HEAD de main).

Comando a ejecutar:
```
bash scripts/deploy.sh $ARGUMENTS
```
