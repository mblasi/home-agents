#!/usr/bin/env zsh
# Wrapper FINO sobre el MOTOR único de deploy (FASE 34). NO reimplementa lógica: invoca
# cloud/bridge/deploy_engine.py en el SER9 por SSH. Toda la lógica de deploy (snapshot, pin de
# ref, install, restart, health-gate, rollback) vive en el motor; este script sólo lo llama.
# Es el invocador LOCAL (cuando Claude opera desde la LAN); el invocador REMOTO es el comando
# deploy.release del cloud-bo, que corre el MISMO motor. Ver D1/D9 en masterplan/estado.md.
#
# Uso:
#   bash scripts/deploy.sh                      # default: core+ear+backoffice a HEAD de main
#   bash scripts/deploy.sh --restart-wa         # + wa
#   bash scripts/deploy.sh --service bridge     # un servicio puntual
#   bash scripts/deploy.sh --ref core=v1.2.3    # pin de un ref (rollback/release fijo)
# Los flags --service/--ref se pasan tal cual al motor (ver deploy_engine.py --help).
set -euo pipefail

ARGS=()
if [[ "${1:-}" == "--restart-wa" ]]; then
  # Compat con la invocación histórica: default + wa.
  ARGS=(--service core --service ear --service backoffice --service wa)
  shift
fi
ARGS+=("$@")

echo "=== Deploy home-agents → capitan-lxc (motor FASE 34) ==="
ssh capitan-lxc \
  "cd ~/workspace/home-agents && ~/home-agents-env/bin/python cloud/bridge/deploy_engine.py ${ARGS[*]}"
echo "=== Deploy completo (health-gate y rollback los maneja el motor) ==="
