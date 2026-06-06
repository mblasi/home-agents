Desplegá home-agents al LXC de producción en el SER9 (capitan-lxc, 192.168.68.132).

El script hace: git pull --recurse-submodules, pip install, restart capitan-core y capitan-backoffice, smoke test.

Pasá `--restart-wa` si también hay que reiniciar el cliente WhatsApp.

Comando a ejecutar:
```
bash scripts/deploy.sh $ARGUMENTS
```
