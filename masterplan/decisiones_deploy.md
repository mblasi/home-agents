# Decisiones del motor de deploy (FASE 34, D1–D9)

Rescatadas de `masterplan/estado.md` al eliminarlo (issue #766). Texto original de las
decisiones consolidadas el 2026-06-20 al tomar la FASE 34; el motor vive en
`cloud/bridge/deploy_engine.py` y su operatoria en `cloud/bridge/README.md` / `AGENTS.md`.

  D1. Brain = ejecutor UNIVERSAL. TODO el deploy (de cualquier componente, en cualquier
      dominio) se dispara como comando del backoffice CLOUD y lo ejecuta el Brain al polearlo
      (egress-only). No hay deploy directo desde la notebook fuera del flujo de comandos. Razón:
      desde fuera de casa la notebook NO tiene ruta a la LAN (Brain/paneles); el único plano de
      control común es el cloud-bo. El `scripts/deploy.sh` local queda como wrapper fino para
      cuando Claude opera DESDE la LAN, invocando el mismo motor.
  D2. El motor tiene UN driver por tipo de target (misma interfaz: snapshot→deploy→health→
      rollback→registro de versión):
        - driver `ser9-service` (core, wa, backoffice-local, ear/audio_server, bridge):
          git pin ref → install si cambió requirements → systemctl restart → health-gate
          (/health) → rollback = checkout del ref del snapshot.
        - driver `panel` (satellite.py/satellite_ui.py por NSPanel): el motor (en la LAN)
          hace el push VERIFICADO (checksum+readback) → restart vía supervisor → health =
          el nodo re-registra en audio_server con su versión → rollback = push del ref previo.
          Absorbe la Etapa E (deploy a paneles robusto) y los footguns de pkill/supervisor.
        - driver `cloudrun` (cloud-bo, oauth-app/meli): `gcloud run deploy --source` (egress
          a GCP) → health-gate = curl a la URL pública → rollback = `gcloud run services
          update-traffic` a la revisión previa (Cloud Run conserva revisiones).
  D3. El Brain requiere credencial gcloud con rol run.admin (+ acceso al build) para el driver
      cloudrun. Sigue siendo EGRESS-ONLY (llama a las APIs de Google, saliente). Aprovisionar.
  D4. Circularidad de la cloud (desplegar cloud-bo y romperla = perder el canal de comandos):
      se mitiga con health-gate + rollback automático a la revisión previa de Cloud Run que el
      propio Brain dispara (no depende de la cloud para revertir). Escape hatch documentado:
      `gcloud run deploy` manual desde la notebook si el rollback automático también falla.
  D5. Feedback rico con LOGS EN VIVO (requisito de UX): el modelo de comandos pasa de
      fire-and-result a PROGRESO INCREMENTAL — el motor emite líneas de log; el bridge las
      postea append-only (Firestore) por comando; el cloud-bo las polea y las muestra en
      streaming durante el deploy. La consola local tail-ea el log del motor directo. Aplica a
      deploys disparados desde cloud-bo Y desde la consola local.
  D6. Visualización de versión (requisito de UX): la versión corriendo de CADA componente, con
      LINK a la versión tageada en GitHub (release), se muestra en LOS DOS backoffices (local y
      cloud). Es la matriz dispositivo×componente→versión de 34.14, con deep-link al release.
  D7. Atomicidad POR-COMPONENTE (no por-release): si un release toca varios componentes y uno
      falla su health-gate, sólo ESE componente revierte a su snapshot; los demás (sanos) quedan
      desplegados. No se revierte un componente sano porque otro falló. (Confirmado 2026-06-20.)
  D8. Versionado SEMVER (vX.Y.Z) por componente; el tag vive en el repo de cada componente
      (core/ear/umbrella) y el GitHub Release referencia ese tag. El bump (patch auto vs
      minor/major explícito) se define en 34.12. (Confirmado 2026-06-20.)
  D9. El driver cloudrun usa una SA de deploy DEDICADA (separada de runtime y bridge SA), con
      permiso mínimo: run.admin (deploy + update-traffic/rollback), cloudbuild.builds.editor,
      artifactregistry.writer, iam.serviceAccountUser (actuar como la runtime SA), storage sobre
      el bucket de staging de Cloud Build. Key JSON en el Brain (egress-only). Script idempotente:
      cloud/infra/provision_deploy_sa.sh. (Confirmado 2026-06-20.)
      ACTIVADO Y PROBADO (2026-06-21, T4a): driver cloudrun deploya el cloud-bo desde el Brain
      end-to-end (build en Cloud Build → deploy → health → ok), y el rollback automático a la
      revisión previa quedó validado (en intentos fallidos por permisos, el cloud-bo se restauró
      sano solo). Hecho: gcloud CLI instalado en el Brain; SA capitan-deployer con run.admin +
      cloudbuild.builds.editor + artifactregistry.writer + storage.admin + logging.viewer
      (proyecto) + actAs sobre runtime SA del cloud-bo y la default compute SA del build; key JSON
      en ~/.config/capitan/deployer-key.json del Brain + SA activada en gcloud (root). Permisos
      reproducibles en cloud/infra/provision_deploy_sa.sh. FALTA: capitan-oauth como 2º target
      (otra región us-east1 + env vars/secrets); driver panel (34.13 T4b).
