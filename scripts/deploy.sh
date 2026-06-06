#!/usr/bin/env zsh
# Deploy home-agents al LXC de producción en el SER9.
# Uso: bash scripts/deploy.sh [--restart-wa]

set -euo pipefail

RESTART_WA=0
[[ "${1:-}" == "--restart-wa" ]] && RESTART_WA=1

echo "=== Deploy home-agents → capitan-lxc ==="

ssh capitan-lxc "
  set -e
  cd ~/workspace/home-agents
  git pull --recurse-submodules
  ~/home-agents-env/bin/pip install -q -r core/requirements.txt
  ~/home-agents-env/bin/pip install -q -r backoffice/requirements.txt
  systemctl --user restart capitan-core capitan-backoffice
  echo 'Servicios reiniciados.'
"

if [[ $RESTART_WA -eq 1 ]]; then
  echo "Reiniciando WA..."
  ssh capitan-lxc "systemctl --user restart capitan-wa 2>/dev/null || echo 'WA no está como servicio — reiniciá manualmente'"
fi

echo "=== Smoke test (esperando 40s para warmup de entity index) ==="
sleep 40
ssh capitan-lxc "curl -sf http://localhost:8765/health" && echo "core OK" || echo "core NO responde"
ssh capitan-lxc "curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/" | grep -qE '^(200|307)' && echo "backoffice OK" || echo "backoffice NO responde"

echo "=== Deploy completo ==="
