#!/usr/bin/env bash
# Provisiona la SA de DEPLOY para el driver cloudrun del motor de deploy (FASE 34, D9).
# El Brain la usa para desplegar Cloud Run (cloud-bo + oauth-app) y revertir revisiones.
# Idempotente: se puede correr varias veces. Egress-only: el Brain llama a las APIs de
# Google (saliente); no abre nada en casa.
#
# Permiso MÍNIMO para `gcloud run deploy --source` + rollback:
#   - run.admin               : deploy de servicios + update-traffic (rollback a revisión previa)
#   - cloudbuild.builds.editor: build de la imagen desde source
#   - artifactregistry.writer : push de la imagen al registry
#   - iam.serviceAccountUser  : actuar como la runtime SA de cada servicio al desplegarlo
#   - storage.admin (acotado) : bucket de staging que usa Cloud Build para el source
#
# Tras correrlo: copiar la key JSON generada al Brain y apuntar GOOGLE_APPLICATION_CREDENTIALS
# del entorno del motor a ese archivo (ver instrucciones al final).
set -euo pipefail

PROJECT="${PROJECT:-capitan-495518}"
REGION="${REGION:-southamerica-east1}"
DEPLOY_SA="${DEPLOY_SA:-capitan-deployer}"
RUNTIME_SA="${RUNTIME_SA:-capitan-cloud-run}"            # runtime SA del cloud-bo
OAUTH_RUNTIME_SA="${OAUTH_RUNTIME_SA:-}"                 # runtime SA de oauth-app, si difiere
KEY_OUT="${KEY_OUT:-./capitan-deployer-key.json}"       # NO commitear (gitignored)

DEPLOY_SA_EMAIL="${DEPLOY_SA}@${PROJECT}.iam.gserviceaccount.com"
RUNTIME_SA_EMAIL="${RUNTIME_SA}@${PROJECT}.iam.gserviceaccount.com"

gcloud config set project "$PROJECT" >/dev/null
echo "== Proyecto: $PROJECT  Región: $REGION  Deploy SA: $DEPLOY_SA_EMAIL =="

# IAM es de consistencia EVENTUAL: una SA recién creada tarda unos segundos en ser visible
# para los add-iam-policy-binding (fallan con "does not exist"). Reintentar con backoff.
_retry() {
  local n=0 max=8
  until "$@"; do
    n=$((n+1))
    if [[ $n -ge $max ]]; then
      echo "   ✗ falló tras $max intentos: $*" >&2
      return 1
    fi
    echo "   · reintento $n/$max (propagación IAM)…" >&2
    sleep 5
  done
}

echo "== APIs (idempotente) =="
gcloud services enable \
  run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  storage.googleapis.com --project "$PROJECT"

echo "== Service Account de deploy =="
if gcloud iam service-accounts describe "$DEPLOY_SA_EMAIL" >/dev/null 2>&1; then
  echo "   · ya existe."
else
  gcloud iam service-accounts create "$DEPLOY_SA" \
    --display-name="Capitán deployer (Brain) — deploy Cloud Run, permiso mínimo"
  # Esperar a que la SA propague antes de referenciarla en los bindings.
  _retry gcloud iam service-accounts describe "$DEPLOY_SA_EMAIL" >/dev/null 2>&1 || true
fi

echo "== Roles a nivel proyecto (deploy + build + rollback de Cloud Run desde source) =="
# Verificados con un deploy real de `gcloud run deploy --source` desde el Brain (FASE 34 T4a):
#  - run.admin               : deploy de servicios + update-traffic (rollback a revisión previa)
#  - cloudbuild.builds.editor: build remoto del source en Cloud Build
#  - artifactregistry.writer : push de la imagen
#  - storage.admin           : `--source` sube el tarball al bucket de staging
#    (run-sources-<project>-<region>) y necesita storage.buckets.list a nivel PROYECTO; el
#    binding por-bucket no alcanza.
#  - logging.viewer          : leer logs del build
for ROLE in \
  roles/run.admin \
  roles/cloudbuild.builds.editor \
  roles/artifactregistry.writer \
  roles/storage.admin \
  roles/logging.viewer ; do
  _retry gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:${DEPLOY_SA_EMAIL}" \
    --role="$ROLE" --condition=None >/dev/null
  echo "   + $ROLE"
done

echo "== actAs sobre las runtime SA + la compute SA del build =="
# Cloud Run deploy requiere actuar como la runtime SA del servicio Y como la SA que Cloud Build
# usa para el build (la default compute SA, salvo que se configure otra).
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
for ACT_SA in "$RUNTIME_SA_EMAIL" "${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"; do
  _retry gcloud iam service-accounts add-iam-policy-binding "$ACT_SA" \
    --member="serviceAccount:${DEPLOY_SA_EMAIL}" \
    --role="roles/iam.serviceAccountUser" >/dev/null
  echo "   + actAs ${ACT_SA}"
done
if [[ -n "$OAUTH_RUNTIME_SA" ]]; then
  _retry gcloud iam service-accounts add-iam-policy-binding \
    "${OAUTH_RUNTIME_SA}@${PROJECT}.iam.gserviceaccount.com" \
    --member="serviceAccount:${DEPLOY_SA_EMAIL}" \
    --role="roles/iam.serviceAccountUser" >/dev/null
  echo "   + actAs ${OAUTH_RUNTIME_SA}@${PROJECT}.iam.gserviceaccount.com"
fi

echo "== Key JSON (para el Brain) =="
if [[ -f "$KEY_OUT" ]]; then
  echo "   · $KEY_OUT ya existe — no se regenera (borralo para rotar)."
else
  gcloud iam service-accounts keys create "$KEY_OUT" \
    --iam-account="$DEPLOY_SA_EMAIL"
  echo "   ✓ key escrita en $KEY_OUT (NO commitear)"
fi

cat <<EOF

=== Listo. Próximo paso en el Brain ===
1) Copiar la key al LXC (fuera del repo):
     scp $KEY_OUT capitan-lxc:~/.config/capitan/deployer-key.json
2) En el entorno del motor (bridge.env / unit del bridge) exportar:
     GOOGLE_APPLICATION_CREDENTIALS=\$HOME/.config/capitan/deployer-key.json
3) Verificar (egress-only, saliente):
     ssh capitan-lxc 'gcloud auth activate-service-account --key-file ~/.config/capitan/deployer-key.json \\
       && gcloud run services list --region $REGION'

La key da poder de deploy: mantenerla fuera del repo (gitignored) y rotarla periódicamente.
EOF
