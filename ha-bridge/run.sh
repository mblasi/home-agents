#!/bin/bash
# Wrapper para systemd: reconstruye el entorno de sesión antes de lanzar el agente.
set -e

export HOME=/home/matias
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export LANG=es_AR.UTF-8
export LC_ALL=es_AR.UTF-8

# Cargar variables de .env
set -a
source /home/matias/ai-lab/.env
set +a

cd /home/matias/ai-lab
exec /home/matias/ai-env/bin/python ha-bridge/listen.py
