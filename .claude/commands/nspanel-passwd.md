Cambiá el password de SSH de Termux en un NSPanel Pro sin necesidad de tener el panel físicamente.

Uso: `/nspanel-passwd <nueva_password> [IP]`
Si no se especifica IP, usa 192.168.68.113 (comedor).

Pasos:
1. Conectar ADB
2. Abrir Termux
3. Ejecutar passwd con el nuevo password via input de teclado

Comandos a ejecutar en orden:
```bash
IP="${2:-192.168.68.113}"
PASS="$1"

# Conectar ADB
adb connect "${IP}:5555"

# Abrir Termux
adb -s "${IP}:5555" shell am start -n com.termux/.HomeActivity
sleep 3

# Escribir passwd
adb -s "${IP}:5555" shell input keyboard text "passwd"
adb -s "${IP}:5555" shell input keyevent KEYCODE_ENTER
sleep 1

# Ingresar nueva password dos veces
adb -s "${IP}:5555" shell input keyboard text "$PASS"
adb -s "${IP}:5555" shell input keyevent KEYCODE_ENTER
sleep 1
adb -s "${IP}:5555" shell input keyboard text "$PASS"
adb -s "${IP}:5555" shell input keyevent KEYCODE_ENTER
sleep 1

echo "Password seteado. Iniciando sshd..."
adb -s "${IP}:5555" shell input keyboard text "sshd"
adb -s "${IP}:5555" shell input keyevent KEYCODE_ENTER

echo "Conectate con: ssh -p 8022 -o HostKeyAlgorithms=+ssh-rsa u0_a53@${IP}"
```

Ejecutar extrayendo IP y password de $ARGUMENTS.
