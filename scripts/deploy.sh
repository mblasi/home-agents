#!/usr/bin/env zsh
# Wrapper FINO del deploy por TARGET (FASE 34, 34.15). NO reimplementa lógica: invoca
# cloud/bridge/deploy_cli.py en el Brain por SSH, que resuelve el target al MISMO comando
# tipado que emite el cloud-bo (deploy.release / deploy.cloud / deploy.satellites) y lo corre
# con validate_command + executor.execute — el MISMO funnel que el bridge usa al desencolar un
# comando de la nube. Así desplegar desde Claude (LAN) es idéntico a hacerlo desde el cloud-bo
# (remoto). Toda la lógica (pin, install, restart, health-gate, rollback, tag) vive en el motor.
#
# Uso:
#   bash scripts/deploy.sh                       # services default (core+ear+backoffice) a HEAD
#   bash scripts/deploy.sh core                  # un service del Brain
#   bash scripts/deploy.sh audio_server          # (repo ear)
#   bash scripts/deploy.sh backoffice
#   bash scripts/deploy.sh cloud-bo              # Cloud Run (activa la SA de deploy)
#   bash scripts/deploy.sh panels                # fuerza el pull de TODOS los paneles
#   bash scripts/deploy.sh nspanel-comedor       # fuerza el pull de un panel
#   bash scripts/deploy.sh core --ref core=v1.2.3   # pin de un ref (rollback/release fijo)
#   bash scripts/deploy.sh --restart-wa          # compat: services default + wa
set -euo pipefail

REMOTE_DIR="~/workspace/home-agents"
PY="~/home-agents-env/bin/python"
TAG="${DEPLOY_TAG_RELEASES:-true}"

run_target() {            # $1 = target (puede ser ""), resto = flags (--ref, --json)
  local target="$1"; shift || true
  # cloud-bo: activar la SA de deploy (el bridge ya la tiene en su entorno; acá la activamos
  # para que el camino sea autocontenido). Idempotente.
  if [[ "$target" == "cloud-bo" ]]; then
    ssh brain-ai 'test -f ~/.config/capitan/deployer-key.json && \\
      CLOUDSDK_CORE_DISABLE_PROMPTS=1 gcloud auth activate-service-account \
      --key-file=~/.config/capitan/deployer-key.json >/dev/null 2>&1 || true'
  fi
  ssh brain-ai \
    "cd $REMOTE_DIR && DEPLOY_TAG_RELEASES=$TAG $PY cloud/bridge/deploy_cli.py $target $*"
}

echo "=== Deploy home-agents → brain-ai (target = ${1:-services default}) ==="

# Compat histórico: --restart-wa = deploy de los services default + wa.
if [[ "${1:-}" == "--restart-wa" ]]; then
  shift
  run_target "" "$@"
  run_target "wa" "$@"
  echo "=== Deploy completo ==="
  exit 0
fi

# Primer arg = target (salvo que sea un flag --…, en cuyo caso no hay target).
TARGET=""
if [[ "${1:-}" != "" && "${1:-}" != --* ]]; then
  TARGET="$1"; shift
fi
run_target "$TARGET" "$@"
echo "=== Deploy completo (health-gate y rollback los maneja el motor) ==="
