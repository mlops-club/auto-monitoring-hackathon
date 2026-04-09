#!/usr/bin/env bash
# Deploy the Grafana observability stack to EKS using official Helm charts.
#
# Prerequisites:
#   1. CDK stack deployed:  npx cdk deploy --app "uv run infra/infra.py" --profile subq-sandbox
#   2. kubeconfig set up:   aws eks update-kubeconfig --name auto-monitoring --region us-west-2 --profile subq-sandbox
#   3. Tools installed:     helm, kubectl, envsubst (brew install gettext)
#
# Usage:
#   ./helm/deploy-monitoring.sh
#   AWS_PROFILE=my-profile ./helm/deploy-monitoring.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE="monitoring"
AWS_PROFILE="${AWS_PROFILE:-subq-sandbox}"
AWS_REGION="${AWS_REGION:-us-west-2}"
STACK_NAME="AutoMonitoringEks"

# ─── Pre-flight checks ───────────────────────────────────────────────
for cmd in helm kubectl envsubst aws; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "ERROR: $cmd not found."; exit 1; }
done

# ─── Fetch S3 bucket name from CloudFormation stack outputs ──────────
echo "Fetching S3 bucket name from CloudFormation stack '$STACK_NAME'..."
S3_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='ObsBucketName'].OutputValue" \
  --output text \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE" 2>/dev/null || echo "")

if [[ -z "$S3_BUCKET" || "$S3_BUCKET" == "None" ]]; then
  echo "ERROR: Could not retrieve ObsBucketName from stack '$STACK_NAME'."
  echo ""
  echo "Deploy the CDK stack first:"
  echo "  npx cdk deploy --app 'uv run infra/infra.py' --profile $AWS_PROFILE"
  exit 1
fi

export S3_BUCKET AWS_REGION

echo ""
echo "  S3 Bucket : $S3_BUCKET"
echo "  Region    : $AWS_REGION"
echo "  Namespace : $NAMESPACE"
echo ""

# ─── Add Helm repositories ──────────────────────────────────────────
echo "Adding Helm repositories..."
helm repo add grafana https://grafana.github.io/helm-charts 2>/dev/null || true
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>/dev/null || true
helm repo update

# ─── Helper: deploy a Helm chart with envsubst-templated values ──────
deploy() {
  local name="$1" chart="$2" values_file="$3"
  shift 3

  echo ""
  echo "══════════════════════════════════════════════════════════════"
  echo "  Deploying: $name  ($chart)"
  echo "══════════════════════════════════════════════════════════════"

  envsubst '$S3_BUCKET $AWS_REGION' < "$SCRIPT_DIR/values/$values_file" | \
    helm upgrade --install "$name" "$chart" \
      --namespace "$NAMESPACE" \
      --create-namespace \
      -f - \
      "$@" \
      --wait --timeout 5m

  echo "  ✓ $name deployed"
}

# ─── 1. Storage backends (deploy Mimir first — Tempo pushes metrics to it) ───
deploy mimir          grafana/mimir-distributed                       mimir.yaml
deploy loki           grafana/loki                                    loki.yaml
deploy tempo          grafana/tempo                                   tempo.yaml
deploy pyroscope      grafana/pyroscope                               pyroscope.yaml

# ─── 2. Infrastructure metrics collector ─────────────────────────────
deploy node-exporter  prometheus-community/prometheus-node-exporter   node-exporter.yaml

# ─── 3. Telemetry collector / router ─────────────────────────────────
deploy alloy          grafana/alloy                                   alloy.yaml

# ─── 4. Visualization ───────────────────────────────────────────────
deploy grafana        grafana/grafana                                 grafana.yaml

# ─── Done ────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  All charts deployed successfully!"
echo "══════════════════════════════════════════════════════════════"
echo ""
echo "Access Grafana:"
echo "  kubectl port-forward svc/grafana 3000:80 -n $NAMESPACE"
echo "  Open http://localhost:3000  (admin / changeme)"
echo ""
echo "Send OTLP telemetry to Alloy:"
echo "  gRPC: alloy.$NAMESPACE.svc.cluster.local:4317"
echo "  HTTP: alloy.$NAMESPACE.svc.cluster.local:4318"
echo "  Faro: alloy.$NAMESPACE.svc.cluster.local:12347"
echo ""
echo "Verify pods:"
echo "  kubectl get pods -n $NAMESPACE"
