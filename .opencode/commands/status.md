Mostrá el estado de todos los servicios de home-agents en el Brain.

Incluye: estado de cada servicio systemd, health del core, accesibilidad del backoffice, estado de HAOS, y uso de recursos del LXC.

Comando a ejecutar:
```bash
ssh capitan-lxc "
echo '=== Servicios ==='
systemctl --user status capitan-core capitan-backoffice capitan-wa --no-pager | grep -E '\.service|Active|Main PID'
echo ''
echo '=== Health core ==='
curl -sf http://localhost:8765/health || echo 'NO RESPONDE'
echo ''
echo '=== HAOS ==='
curl -sf http://192.168.68.101:8123/api/ -H 'Authorization: Bearer $(grep HAOS_TOKEN ~/workspace/home-agents/.env | cut -d= -f2)' > /dev/null && echo 'OK' || echo 'NO RESPONDE'
echo ''
echo '=== Recursos ==='
free -h | head -2
df -h / | tail -1
"
```
