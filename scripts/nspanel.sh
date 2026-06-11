#!/usr/bin/env zsh
# Administración de NSPanel Pro vía ADB y SSH
# Uso: scripts/nspanel.sh <comando> [args]

set -euo pipefail

NSPANEL_IP="${NSPANEL_IP:-192.168.68.113}"
NSPANEL_ADB="${NSPANEL_IP}:5555"
NSPANEL_SSH_PORT=8022
TERMUX_USER="u0_a53"
HA_COMPANION="io.homeassistant.companion.android.minimal/io.homeassistant.companion.android.launch.LaunchActivity"
TERMUX_ACTIVITY="com.termux/.HomeActivity"
BOOT_SCRIPT="/data/data/com.termux/files/home/.termux/boot/start-ha.sh"

adb_cmd() { adb -s "$NSPANEL_ADB" "$@"; }

cmd_connect() {
    echo "Conectando ADB a $NSPANEL_ADB..."
    adb connect "$NSPANEL_ADB"
}

cmd_disconnect() {
    adb disconnect "$NSPANEL_ADB"
}

cmd_ssh() {
    echo "Conectando SSH a $NSPANEL_IP:$NSPANEL_SSH_PORT..."
    ssh -p "$NSPANEL_SSH_PORT" "${TERMUX_USER}@${NSPANEL_IP}"
}

cmd_status() {
    echo "=== Foco actual ==="
    adb_cmd shell dumpsys window | grep mCurrentFocus
    echo "\n=== Apps en foreground ==="
    adb_cmd shell dumpsys activity | grep "mResumedActivity"
    echo "\n=== Audio ==="
    adb_cmd shell dumpsys audio | grep -E "STREAM_MUSIC|Devices:" | head -6
}

cmd_reboot() {
    echo "Reiniciando $NSPANEL_IP..."
    adb_cmd shell reboot
}

cmd_open_ha() {
    adb_cmd shell am start -n "$HA_COMPANION"
}

cmd_open_termux() {
    adb_cmd shell am start -n "$TERMUX_ACTIVITY"
}

cmd_start_sshd() {
    adb_cmd shell am start -n "$TERMUX_ACTIVITY"
    sleep 2
    adb_cmd shell input keyboard text "sshd"
    adb_cmd shell input keyevent KEYCODE_ENTER
    echo "sshd iniciado. Conectate con: ssh -p $NSPANEL_SSH_PORT ${TERMUX_USER}@${NSPANEL_IP}"
}

cmd_boot_script() {
    echo "=== Boot script actual ==="
    adb_cmd shell su u0_a53 -c "cat $BOOT_SCRIPT" 2>/dev/null || \
        adb_cmd shell cat "$BOOT_SCRIPT" 2>/dev/null || \
        echo "(no se pudo leer — iniciá sshd y usá: ssh -p $NSPANEL_SSH_PORT ${TERMUX_USER}@${NSPANEL_IP} cat ~/.termux/boot/start-ha.sh)"
}

cmd_update_boot() {
    local url="${1:-}"
    if [[ -z "$url" ]]; then
        echo "Uso: nspanel.sh update-boot <url>"
        echo "Ejemplo: nspanel.sh update-boot http://192.168.68.101:8123/dashboard-comedor/0"
        exit 1
    fi
    # Escribe via SSH (única forma confiable por restricciones SELinux)
    echo "Actualizando boot script via SSH..."
    ssh -p "$NSPANEL_SSH_PORT" "${TERMUX_USER}@${NSPANEL_IP}" \
        "cat > ~/.termux/boot/start-ha.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
sleep 10
am start -n $HA_COMPANION -d $url
EOF
chmod +x ~/.termux/boot/start-ha.sh && echo 'OK' && cat ~/.termux/boot/start-ha.sh"
}

cmd_install_base() {
    echo "=== Setup inicial NSPanel Pro ==="
    echo "Paso 1: Conectar ADB"
    cmd_connect

    echo "\nPaso 2: Instalar Termux"
    local termux_apk="termux-app_v0.118.3+github-debug_arm64-v8a.apk"
    if [[ ! -f "/tmp/$termux_apk" ]]; then
        wget -O "/tmp/$termux_apk" \
            "https://github.com/termux/termux-app/releases/download/v0.118.3/$termux_apk"
    fi
    adb_cmd install "/tmp/$termux_apk" && echo "Termux instalado"

    echo "\nPaso 3: Instalar Termux:Boot"
    local boot_apk="termux-boot-app_v0.8.1+github.debug.apk"
    if [[ ! -f "/tmp/$boot_apk" ]]; then
        wget -O "/tmp/$boot_apk" \
            "https://github.com/termux/termux-boot/releases/download/v0.8.1/$boot_apk"
    fi
    adb_cmd install "/tmp/$boot_apk" && echo "Termux:Boot instalado"

    echo "\nPaso 4: Instalar HA Companion (minimal)"
    local ha_apk="app-minimal-release.apk"
    if [[ ! -f "/tmp/$ha_apk" ]]; then
        wget -O "/tmp/$ha_apk" \
            "https://github.com/home-assistant/android/releases/latest/download/$ha_apk"
    fi
    adb_cmd install "/tmp/$ha_apk" && echo "HA Companion instalado"

    echo "\nPaso 5: Abrir Termux:Boot para registrarlo"
    adb_cmd shell am start -n "com.termux.boot/.BootActivity"

    echo "\nSetup base completo."
    echo "Siguiente paso: abrir Termux, correr 'pkg update && pkg install python portaudio openssh', setear password con 'passwd', y ejecutar 'nspanel.sh update-boot <url>'"
}

cmd_packages() {
    echo "Instalando paquetes Python en Termux via SSH..."
    ssh -p "$NSPANEL_SSH_PORT" "${TERMUX_USER}@${NSPANEL_IP}" \
        "pkg update -y && pkg install -y python portaudio && pip install sounddevice"
}

ssh_panel() { ssh -p "$NSPANEL_SSH_PORT" -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa \
    -o StrictHostKeyChecking=no -o ConnectTimeout=8 "${TERMUX_USER}@${NSPANEL_IP}" "$@"; }
scp_panel() { scp -P "$NSPANEL_SSH_PORT" -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa \
    -o StrictHostKeyChecking=no "$@"; }
pkg_installed() { adb_cmd shell pm list packages 2>/dev/null | grep -q "package:$1"; }

# Provisioning completo de un panel nuevo (16.24). Idempotente: saltea lo ya hecho.
# Uso: nspanel.sh provision <name> <room> [ip]
cmd_provision() {
    local name="${1:-}" room="${2:-}" ip="${3:-$NSPANEL_IP}"
    if [[ -z "$name" || -z "$room" ]]; then
        echo "Uso: nspanel.sh provision <name> <room> [ip]"; exit 1
    fi
    NSPANEL_IP="$ip"; NSPANEL_ADB="${ip}:5555"
    local NODE_ID="nspanel-${name}"
    local REPO="$(cd "$(dirname "$0")/.." && pwd)"
    local AUDIO_URL="${AUDIO_SERVER_URL:-http://192.168.68.132:8766}"
    echo "=== Provisioning panel '$name' (room=$room, ip=$ip, node=$NODE_ID) ==="

    echo "\n[1/9] ADB — conectividad"
    if ! adb connect "$NSPANEL_ADB" 2>/dev/null | grep -qE "connected|already"; then
        echo "  ✗ no se pudo conectar ADB a $NSPANEL_ADB."
        echo "  PREREQUISITO FÍSICO: habilitá ADB en el panel (Settings → About → tapear build)."
        exit 1
    fi
    echo "  ✓ ADB conectado"

    echo "\n[2/9] Apps base (Termux, Termux:Boot, HA Companion)"
    pkg_installed com.termux           && echo "  ✓ Termux ya" || { cmd_install_base; }
    echo "\n[3/9] Termux:API + Termux:GUI (mic + overlay)"
    if pkg_installed com.termux.api; then echo "  ✓ Termux:API ya"; else
        wget -qO /tmp/termux-api.apk "https://github.com/termux/termux-api/releases/download/v0.53.0/termux-api-app_v0.53.0%2Bgithub.debug.apk"
        adb_cmd install /tmp/termux-api.apk && echo "  ✓ Termux:API"; fi
    if pkg_installed com.termux.gui; then echo "  ✓ Termux:GUI ya"; else
        wget -qO /tmp/termux-gui.apk "https://github.com/termux/termux-gui/releases/download/0.1.6/app-release.apk"
        adb_cmd install /tmp/termux-gui.apk && echo "  ✓ Termux:GUI"; fi
    adb_cmd shell "monkey -p com.termux.gui -c android.intent.category.LAUNCHER 1" >/dev/null 2>&1
    adb_cmd shell appops set com.termux.gui SYSTEM_ALERT_WINDOW allow 2>/dev/null || true
    adb_cmd shell pm grant com.termux.api android.permission.RECORD_AUDIO 2>/dev/null || true
    echo "  ✓ permisos (overlay + mic)"

    echo "\n[4/9] SSH — key auth (bootstrap vía adb, sin password manual)"
    # Asegurar sshd corriendo
    adb_cmd shell "am start -n $TERMUX_ACTIVITY" >/dev/null 2>&1; sleep 1
    if ! ssh_panel "echo ok" 2>/dev/null | grep -q ok; then
        # Empujar la pubkey local al authorized_keys del panel usando root (adb su)
        local PUB; PUB="$(cat "$HOME/.ssh/id_ed25519.pub" 2>/dev/null || cat "$HOME/.ssh/id_rsa.pub" 2>/dev/null || true)"
        if [[ -z "$PUB" ]]; then ssh-keygen -t ed25519 -N "" -f "$HOME/.ssh/id_ed25519" -q; PUB="$(cat "$HOME/.ssh/id_ed25519.pub")"; fi
        local HT="/data/data/com.termux/files/home"
        adb_cmd shell "su -c \"mkdir -p $HT/.ssh && echo '$PUB' >> $HT/.ssh/authorized_keys && chown -R u0_a53:u0_a53 $HT/.ssh && chmod 700 $HT/.ssh && chmod 600 $HT/.ssh/authorized_keys\"" >/dev/null 2>&1
        # arrancar sshd si no estaba
        adb_cmd shell "am start -n $TERMUX_ACTIVITY" >/dev/null 2>&1; sleep 1
        adb_cmd shell input keyboard text "sshd" >/dev/null 2>&1; adb_cmd shell input keyevent KEYCODE_ENTER >/dev/null 2>&1; sleep 2
    fi
    if ! ssh_panel "echo ok" 2>/dev/null | grep -q ok; then
        echo "  ✗ SSH sigue sin responder tras el bootstrap de key."
        echo "    Verificá que sshd corra en Termux (panel) y reintentá (idempotente)."
        exit 1
    fi
    echo "  ✓ SSH key-auth OK"

    echo "\n[5/9] Dependencias (pkg + pip) + patch openwakeword"
    ssh_panel 'export PATH=/data/data/com.termux/files/usr/bin:$PATH
        pkg install -y python portaudio onnxruntime termux-api openssh >/dev/null 2>&1
        pip install -q sounddevice requests numpy tqdm termuxgui >/dev/null 2>&1
        pip install -q --no-deps openwakeword >/dev/null 2>&1
        OWW=$(python3.13 -c "import openwakeword,os;print(os.path.dirname(openwakeword.__file__))" 2>/dev/null)
        if [ -n "$OWW" ]; then sed -i "s/^from openwakeword.custom_verifier_model import train_custom_verifier/try:\n    from openwakeword.custom_verifier_model import train_custom_verifier\nexcept ImportError:\n    train_custom_verifier = None/" "$OWW/__init__.py" 2>/dev/null; fi
        echo deps-ok' 2>&1 | grep -q deps-ok && echo "  ✓ dependencias" || echo "  ⚠ revisar deps manualmente"

    echo "\n[6/9] Modelos + satellite.py"
    ssh_panel "mkdir -p ~/wakeword ~/.config ~/assets ~/.termux/boot" 2>/dev/null
    # modelos estáticos (melspec/embedding) desde el venv del laptop; capitan.onnx lo baja el satellite (16.17)
    local OWW_RES="$HOME/home-agents-env/lib/python3.13/site-packages/openwakeword/resources/models"
    [[ -f "$OWW_RES/melspectrogram.onnx" ]] && scp_panel "$OWW_RES/melspectrogram.onnx" "$OWW_RES/embedding_model.onnx" "${TERMUX_USER}@${ip}:~/wakeword/" 2>/dev/null && echo "  ✓ modelos de features"
    [[ -f "$HOME/.local/share/wakeword/capitan.onnx" ]] && scp_panel "$HOME/.local/share/wakeword/capitan.onnx" "${TERMUX_USER}@${ip}:~/wakeword/" 2>/dev/null && echo "  ✓ capitan.onnx (semilla)"
    scp_panel "$REPO/ear/satellite.py" "$REPO/ear/satellite_ui.py" "${TERMUX_USER}@${ip}:~/" 2>/dev/null && echo "  ✓ satellite.py + ui"
    [[ -f "$REPO/ear/assets/wakeword_ack.wav" ]] && scp_panel "$REPO/ear/assets/wakeword_ack.wav" "${TERMUX_USER}@${ip}:~/assets/" 2>/dev/null

    echo "\n[7/9] satellite.env (node=$NODE_ID room=$room)"
    ssh_panel "cat > ~/.config/satellite.env" <<EOF
AUDIO_SERVER_URL=$AUDIO_URL
NODE_ID=$NODE_ID
ROOM=$room
WAKEWORD_MODEL=/data/data/com.termux/files/home/wakeword/capitan.onnx
MELSPEC_MODEL=/data/data/com.termux/files/home/wakeword/melspectrogram.onnx
EMBEDDING_MODEL=/data/data/com.termux/files/home/wakeword/embedding_model.onnx
WAKEWORD_THRESH=0.7
COMMAND_SECS=5
SAMPLE_RATE=16000
EOF
    echo "  ✓ satellite.env"

    echo "\n[8/9] Boot script"
    ssh_panel "cat > ~/.termux/boot/start-ha.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
export PATH=/data/data/com.termux/files/usr/bin:$PATH
sshd
sleep 10
monkey -p com.termux.gui -c android.intent.category.LAUNCHER 1
am start -n io.homeassistant.companion.android.minimal/io.homeassistant.companion.android.launch.LaunchActivity
sleep 15
nohup python3.13 ~/satellite.py >> ~/.satellite.log 2>&1 &
EOF
    ssh_panel "chmod +x ~/.termux/boot/start-ha.sh" 2>/dev/null
    adb_cmd shell am start -n "com.termux.boot/.BootActivity" >/dev/null 2>&1
    echo "  ✓ boot script + Termux:Boot registrado"

    echo "\n[9/9] Registrar el panel en la DB (vía el core)"
    local CORE="${CORE_URL:-http://192.168.68.132:8765}"
    if curl -s -X POST "$CORE/panels" -H 'Content-Type: application/json' \
        -d "{\"name\":\"$name\",\"room\":\"$room\",\"ip\":\"$ip\",\"node_id\":\"$NODE_ID\"}" \
        -o /dev/null -w '%{http_code}' 2>/dev/null | grep -q '^2'; then
        echo "  ✓ registrado en la DB"
    else
        echo "  ⚠ no se pudo registrar en el core ($CORE/panels) — registralo desde el backoffice /panels"
    fi

    echo "\n=== Provisioning de '$name' completo ==="
    echo "FALTA (manual): crear usuario HA 'nspanel-$name' + dashboard del ambiente, y reiniciar el panel:"
    echo "  NSPANEL_IP=$ip bash scripts/nspanel.sh reboot"
}

cmd_help() {
    cat << 'EOF'
Uso: scripts/nspanel.sh <comando> [args]

Variables de entorno:
  NSPANEL_IP   IP del panel (default: 192.168.68.113)

Comandos:
  connect          Conectar ADB over WiFi
  disconnect       Desconectar ADB
  ssh              Abrir shell SSH en Termux
  status           Mostrar estado actual (foco, audio)
  reboot           Reiniciar el panel
  open-ha          Lanzar HA Companion App
  open-termux      Lanzar Termux
  start-sshd       Iniciar sshd en Termux (via ADB)
  boot-script      Ver el script de arranque actual
  update-boot <url> Actualizar dashboard de arranque (via SSH)
  install-base     Setup completo desde cero (Termux + Boot + HA Companion)
  packages         Instalar Python + sounddevice en Termux (via SSH)
  provision <name> <room> [ip]  Bootstrap COMPLETO de un panel nuevo (idempotente):
                   apps, deps, modelos, satellite, boot script, registro en panels.yaml.
                   Prereqs físicos: habilitar ADB + setear password SSH (passwd).
  help             Mostrar esta ayuda

Ejemplos:
  scripts/nspanel.sh provision dormitorio dormitorio 192.168.68.114
  NSPANEL_IP=192.168.68.114 scripts/nspanel.sh connect
  scripts/nspanel.sh update-boot http://192.168.68.101:8123/dashboard-dormitorio/0
  scripts/nspanel.sh ssh
EOF
}

case "${1:-help}" in
    connect)       cmd_connect ;;
    disconnect)    cmd_disconnect ;;
    ssh)           cmd_ssh ;;
    status)        cmd_status ;;
    reboot)        cmd_reboot ;;
    open-ha)       cmd_open_ha ;;
    open-termux)   cmd_open_termux ;;
    start-sshd)    cmd_start_sshd ;;
    boot-script)   cmd_boot_script ;;
    update-boot)   cmd_update_boot "${2:-}" ;;
    install-base)  cmd_install_base ;;
    packages)      cmd_packages ;;
    provision)     cmd_provision "${2:-}" "${3:-}" "${4:-}" ;;
    help|--help|-h) cmd_help ;;
    *)
        echo "Comando desconocido: $1"
        cmd_help
        exit 1
        ;;
esac
