#!/usr/bin/env bash
# Configura Firebase Auth (Google sign-in) para el dashboard. FASE 33 (33.8).
# Idempotente. Requiere gcloud autenticado con permisos de Owner/Editor + Firebase.
#
# Hace: addFirebase → web app → habilitar proveedor Google → authorized domains →
#       fijar FIREBASE_API_KEY/FIREBASE_AUTH_DOMAIN en el servicio Cloud Run.
set -euo pipefail

PROJECT="${PROJECT:-capitan-495518}"
REGION="${REGION:-southamerica-east1}"
SERVICE="${SERVICE:-capitan-cloud}"
WEBAPP_DISPLAY="capitan-dashboard"

H_AUTH() { echo "Authorization: Bearer $(gcloud auth print-access-token)"; }
QP="x-goog-user-project: ${PROJECT}"
FB="https://firebase.googleapis.com/v1beta1"
IT="https://identitytoolkit.googleapis.com/admin/v2"

echo "== Asegurar Firebase en el proyecto =="
gcloud services enable firebase.googleapis.com --project "$PROJECT" >/dev/null
curl -s -X POST "${FB}/projects/${PROJECT}:addFirebase" \
  -H "$(H_AUTH)" -H "$QP" -H "Content-Type: application/json" -d '{}' >/dev/null || true
sleep 8

echo "== Web app =="
APP_ID="$(curl -s "${FB}/projects/${PROJECT}/webApps" -H "$(H_AUTH)" -H "$QP" \
  | python3 -c 'import sys,json; a=json.load(sys.stdin).get("apps",[]); print(a[0]["appId"] if a else "")')"
if [ -z "$APP_ID" ]; then
  curl -s -X POST "${FB}/projects/${PROJECT}/webApps" -H "$(H_AUTH)" -H "$QP" \
    -H "Content-Type: application/json" -d "{\"displayName\":\"${WEBAPP_DISPLAY}\"}" >/dev/null
  sleep 8
  APP_ID="$(curl -s "${FB}/projects/${PROJECT}/webApps" -H "$(H_AUTH)" -H "$QP" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["apps"][0]["appId"])')"
fi
echo "   appId: $APP_ID"

CFG="$(curl -s "${FB}/projects/${PROJECT}/webApps/${APP_ID}/config" -H "$(H_AUTH)" -H "$QP")"
API_KEY="$(echo "$CFG" | python3 -c 'import sys,json; print(json.load(sys.stdin)["apiKey"])')"
AUTH_DOMAIN="$(echo "$CFG" | python3 -c 'import sys,json; print(json.load(sys.stdin)["authDomain"])')"
echo "   apiKey: ${API_KEY:0:12}...  authDomain: $AUTH_DOMAIN"

echo "== Habilitar proveedor Google (OAuth Google-managed) =="
curl -s -X POST "${IT}/projects/${PROJECT}/defaultSupportedIdpConfigs?idpId=google.com" \
  -H "$(H_AUTH)" -H "$QP" -H "Content-Type: application/json" \
  -d '{"enabled": true}' >/dev/null 2>&1 || \
curl -s -X PATCH "${IT}/projects/${PROJECT}/defaultSupportedIdpConfigs/google.com?updateMask=enabled" \
  -H "$(H_AUTH)" -H "$QP" -H "Content-Type: application/json" -d '{"enabled": true}' >/dev/null

echo "== Authorized domains (agregar dominio de Cloud Run) =="
RUN_HOST="$(gcloud run services describe "$SERVICE" --region "$REGION" \
  --format='value(status.url)' | sed 's#https://##')"
CUR="$(curl -s "${IT}/projects/${PROJECT}/config" -H "$(H_AUTH)" -H "$QP")"
NEW_DOMAINS="$(echo "$CUR" | RUN_HOST="$RUN_HOST" python3 -c '
import sys, json, os
cfg = json.load(sys.stdin)
doms = cfg.get("authorizedDomains", [])
h = os.environ["RUN_HOST"]
if h not in doms: doms.append(h)
print(json.dumps(doms))')"
curl -s -X PATCH "${IT}/projects/${PROJECT}/config?updateMask=authorizedDomains" \
  -H "$(H_AUTH)" -H "$QP" -H "Content-Type: application/json" \
  -d "{\"authorizedDomains\": ${NEW_DOMAINS}}" >/dev/null
echo "   dominios: $NEW_DOMAINS"

echo "== Fijar config web en Cloud Run =="
gcloud run services update "$SERVICE" --region "$REGION" \
  --update-env-vars="FIREBASE_API_KEY=${API_KEY},FIREBASE_AUTH_DOMAIN=${AUTH_DOMAIN}" >/dev/null

echo "== LISTO — login Google habilitado =="
