#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="tfc-checkin-1761"
USER_EMAIL="mike@fitclinic.io"
BILLING_ACCOUNT_ID="018F7C-893133-6263FA"
GRANT_TO_USER="user:${USER_EMAIL}"

gcloud config set project "$PROJECT_ID"

# Link billing
gcloud beta billing projects link "$PROJECT_ID" \
  --billing-account="$BILLING_ACCOUNT_ID" || true

# APIs
SERVICES=(
  serviceusage.googleapis.com
  cloudresourcemanager.googleapis.com
  iam.googleapis.com
  iamcredentials.googleapis.com
  cloudbilling.googleapis.com
  sts.googleapis.com
  sheets.googleapis.com
  aiplatform.googleapis.com
  appengine.googleapis.com
  integrations.googleapis.com
  artifactregistry.googleapis.com
  bigquery.googleapis.com
  cloudbuild.googleapis.com
  clouddeploy.googleapis.com
  cloudkms.googleapis.com
  language.googleapis.com
  run.googleapis.com
  cloudfunctions.googleapis.com
  sourcerepo.googleapis.com
  storage.googleapis.com
  vision.googleapis.com
  compute.googleapis.com
  firestore.googleapis.com
  monitoring.googleapis.com
  logging.googleapis.com
  container.googleapis.com
  pubsub.googleapis.com
  recaptchaenterprise.googleapis.com
  secretmanager.googleapis.com
  securitycenter.googleapis.com
  speech.googleapis.com
  videointelligence.googleapis.com
  webrisk.googleapis.com
  workflows.googleapis.com
  workloadmanager.googleapis.com
  spanner.googleapis.com
  alloydb.googleapis.com
  firebase.googleapis.com
  maps-backend.googleapis.com
)

echo "Enabling APIs..."
gcloud services enable "${SERVICES[@]}"

echo "Granting broad project roles..."
BROAD_ROLES=(
  roles/owner
  roles/editor
  roles/viewer
  roles/resourcemanager.projectIamAdmin
  roles/serviceusage.serviceUsageAdmin
  roles/iam.securityAdmin
  roles/iam.serviceAccountAdmin
  roles/iam.serviceAccountUser
  roles/iam.serviceAccountTokenCreator
  roles/browser
  roles/logging.admin
  roles/monitoring.admin
  roles/storage.admin
  roles/compute.admin
  roles/run.admin
  roles/cloudfunctions.admin
  roles/appengine.appAdmin
  roles/container.admin
  roles/pubsub.admin
  roles/bigquery.admin
  roles/artifactregistry.admin
  roles/secretmanager.admin
  roles/cloudkms.admin
  roles/workflows.admin
  roles/firestore.admin
  roles/spanner.admin
  roles/aiplatform.admin
  roles/firebase.admin
)

for ROLE in "${BROAD_ROLES[@]}"; do
  echo "Granting ${ROLE} to ${GRANT_TO_USER}"
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="$GRANT_TO_USER" \
    --role="$ROLE" --quiet || true
done

echo "Creating a general-purpose service account..."
SA_ID="project-admin"
SA_EMAIL="${SA_ID}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud iam service-accounts create "$SA_ID" \
  --display-name="Project Admin Service Account" || true

echo "Granting broad roles to service account..."
for ROLE in "${BROAD_ROLES[@]}"; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="$ROLE" --quiet || true
done

echo "Allowing user to impersonate service account..."
for ROLE in roles/iam.serviceAccountUser roles/iam.serviceAccountTokenCreator; do
  gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
    --member="$GRANT_TO_USER" \
    --role="$ROLE" || true
done

echo ""
echo "=== Setup complete ==="
echo "Project: $PROJECT_ID"
echo "Service Account: $SA_EMAIL"
echo ""
echo "Next steps:"
echo "  1. Run: gcloud auth application-default login"
echo "  2. Or create a key: gcloud iam service-accounts keys create credentials.json --iam-account=$SA_EMAIL"
