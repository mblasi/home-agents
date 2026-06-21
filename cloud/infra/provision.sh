#!/usr/bin/env bash
# IaC reproducible para el backoffice en la nube (FASE 33 Etapa B/D).
# Idempotente: se puede correr varias veces. Usa gcloud (no Terraform).
#
# Provisiona: APIs, Firestore (native + TTL), Service Accounts (runtime + bridge),
# Secret Manager, y despliega el servicio Cloud Run. La config de Identity Platform
# (proveedor Google + API key web) tiene pasos manuales documentados en README.md.
set -euo pipefail

PROJECT="${PROJECT:-capitan-495518}"
REGION="${REGION:-southamerica-east1}"
SERVICE="${SERVICE:-capitan-cloud}"
RUNTIME_SA="capitan-cloud-run"
BRIDGE_SA="capitan-bridge"
ALLOWED_EMAILS="${ALLOWED_EMAILS:-matias@blasi.ar}"

RUNTIME_SA_EMAIL="${RUNTIME_SA}@${PROJECT}.iam.gserviceaccount.com"
BRIDGE_SA_EMAIL="${BRIDGE_SA}@${PROJECT}.iam.gserviceaccount.com"

gcloud config set project "$PROJECT" >/dev/null
echo "== Proyecto: $PROJECT  Región: $REGION  Servicio: $SERVICE =="

echo "== APIs =="
gcloud services enable \
  run.googleapis.com firestore.googleapis.com secretmanager.googleapis.com \
  identitytoolkit.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  --project "$PROJECT"

echo "== Firestore (native mode) =="
if ! gcloud firestore databases describe --database='(default)' >/dev/null 2>&1; then
  gcloud firestore databases create --location="$REGION" --type=firestore-native
else
  echo "   Firestore ya existe."
fi

echo "== TTL policies =="
gcloud firestore fields ttls update ttl_at \
  --collection-group=commands --enable-ttl --async || true
gcloud firestore fields ttls update expires_at \
  --collection-group=state_history --enable-ttl --async || true

echo "== Service Accounts =="
gcloud iam service-accounts describe "$RUNTIME_SA_EMAIL" >/dev/null 2>&1 || \
  gcloud iam service-accounts create "$RUNTIME_SA" \
    --display-name="Capitán Cloud Run runtime"
gcloud iam service-accounts describe "$BRIDGE_SA_EMAIL" >/dev/null 2>&1 || \
  gcloud iam service-accounts create "$BRIDGE_SA" \
    --display-name="Capitán bridge (Brain) — sin roles, sólo identidad OIDC"

echo "== IAM: runtime SA puede leer/escribir Firestore (permiso mínimo) =="
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:${RUNTIME_SA_EMAIL}" \
  --role="roles/datastore.user" --condition=None >/dev/null
# El bridge SA NO recibe roles de proyecto: sólo se usa su identidad para mintear
# ID tokens OIDC (audience = URL del servicio). Permiso mínimo absoluto.

echo "== Deploy Cloud Run (source-based build) =="
gcloud run deploy "$SERVICE" \
  --source "$(dirname "$0")/.." \
  --region "$REGION" \
  --service-account "$RUNTIME_SA_EMAIL" \
  --allow-unauthenticated \
  --min-instances=0 --max-instances=2 \
  --set-env-vars="GCP_PROJECT=${PROJECT},FIREBASE_PROJECT_ID=${PROJECT},ALLOWED_EMAILS=${ALLOWED_EMAILS},BRIDGE_SA_EMAIL=${BRIDGE_SA_EMAIL}"

URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')"
echo "== Servicio en: $URL =="

echo "== Fijar SERVICE_URL (audience del bridge) + Firebase web config =="
echo "   Completar FIREBASE_API_KEY/FIREBASE_AUTH_DOMAIN tras configurar Identity Platform."
gcloud run services update "$SERVICE" --region "$REGION" \
  --update-env-vars="SERVICE_URL=${URL}"

cat <<EOF

== LISTO ==
Servicio:    $URL
Runtime SA:  $RUNTIME_SA_EMAIL  (roles/datastore.user)
Bridge SA:   $BRIDGE_SA_EMAIL   (sin roles — identidad OIDC para el bridge)

Pasos restantes:
  1. Login del dashboard:  bash infra/setup_firebase.sh   (Firebase + Google sign-in)
  2. Generar key del bridge SA (fuera del repo) para el cloud_bridge.py (Etapa C).
EOF
