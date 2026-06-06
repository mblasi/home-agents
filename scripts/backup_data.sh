#!/usr/bin/env bash
# Backup diario de ~/.local/share/capitan/ en el LXC.
# Retiene 7 días. Ejecutar como cron en capitan-lxc.

set -euo pipefail

DATA_DIR="$HOME/.local/share/capitan"
BACKUP_DIR="$HOME/.local/share/capitan-backups"
DATE=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="$BACKUP_DIR/capitan-$DATE.tar.gz"

mkdir -p "$BACKUP_DIR"

tar -czf "$BACKUP_FILE" \
    --exclude="$DATA_DIR/traces" \
    --exclude="$DATA_DIR/finance_news_index.json" \
    -C "$HOME/.local/share" capitan

# Eliminar backups con más de 7 días
find "$BACKUP_DIR" -name "capitan-*.tar.gz" -mtime +7 -delete

echo "Backup completado: $BACKUP_FILE ($(du -sh "$BACKUP_FILE" | cut -f1))"
