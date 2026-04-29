#!/bin/bash
# Lanza el agente Capitán con dashboard zellij.
# Si el servicio systemd ya está corriendo, solo lo informa y sale.
# Uso: bash ha-bridge/dashboard.sh
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export HOME="${HOME:-/home/matias}"
export XDG_RUNTIME_DIR="/run/user/$(id -u)"

# Verificar si el servicio systemd ya está corriendo
if systemctl --user is-active --quiet capitan.service 2>/dev/null; then
    echo "El servicio capitan ya está corriendo (systemd)."
    echo "Para detenerlo: systemctl --user stop capitan.service"
    exit 1
fi

# Cargar credenciales para que los panes las hereden
set -a
source "$REPO_DIR/.env"
set +a

# Limpiar métricas de sesiones anteriores
rm -rf /tmp/capitan
mkdir -p /tmp/capitan

# Eliminar sesión zellij previa si existe
zellij delete-session capitan --force 2>/dev/null || true

exec zellij --layout "$REPO_DIR/ha-bridge/dashboard.kdl" \
            --session capitan
