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
  help             Mostrar esta ayuda

Ejemplos:
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
    help|--help|-h) cmd_help ;;
    *)
        echo "Comando desconocido: $1"
        cmd_help
        exit 1
        ;;
esac
