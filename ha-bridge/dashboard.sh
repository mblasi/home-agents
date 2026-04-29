#!/bin/bash
# Lanza el agente Capitán con dashboard zellij.
# Uso: bash ha-bridge/dashboard.sh
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Cargar credenciales para que los panes las hereden
set -a
source "$REPO_DIR/.env"
set +a

export HOME="${HOME:-/home/matias}"
export XDG_RUNTIME_DIR="/run/user/$(id -u)"

# Limpiar métricas de sesiones anteriores
rm -rf /tmp/capitan
mkdir -p /tmp/capitan

exec zellij --layout "$REPO_DIR/ha-bridge/dashboard.kdl" \
            --session capitan
