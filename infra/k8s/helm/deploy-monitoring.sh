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
AWS_PROFILE="${AWS_PROFILE:-}"
AWS_REGION="${AWS_REGION:-us-west-2}"
# Build --profile flag only when AWS_PROFILE is set (CI uses env-var creds instead)
PROFILE_FLAG="${AWS_PROFILE:+--profile $AWS_PROFILE}"
STACK_NAME="AutoMonitoringEks"
CLUSTER_NAME="auto-monitoring"

# ─── Pre-flight checks ───────────────────────────────────────────────
for cmd in helm kubectl envsubst aws; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "ERROR: $cmd not found."; exit 1; }
done

# ─── Fetch CloudFormation stack outputs ───────────────────────────────
echo "Fetching outputs from CloudFormation stack '$STACK_NAME'..."

cfn_output() {
  aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" \
    --output text \
    --region "$AWS_REGION" \
    $PROFILE_FLAG 2>/dev/null || echo ""
}

S3_BUCKET=$(cfn_output ObsBucketName)
CERT_ARN=$(cfn_output WildcardCertArn)
LB_CONTROLLER_ROLE_ARN=$(cfn_output LbControllerRoleArn)
EXTERNAL_DNS_ROLE_ARN=$(cfn_output ExternalDnsRoleArn)
ALLOY_ROLE_ARN=$(cfn_output AlloyRoleArn)

for var in S3_BUCKET CERT_ARN LB_CONTROLLER_ROLE_ARN EXTERNAL_DNS_ROLE_ARN ALLOY_ROLE_ARN; do
  val="${!var}"
  if [[ -z "$val" || "$val" == "None" ]]; then
    echo "ERROR: Could not retrieve $var from stack '$STACK_NAME'."
    echo ""
    echo "Deploy the CDK stack first:"
    echo "  npx cdk deploy --app 'uv run infra/infra.py' ${AWS_PROFILE:+--profile $AWS_PROFILE}"
    exit 1
  fi
done

export S3_BUCKET AWS_REGION CERT_ARN

echo "  S3 Bucket  : $S3_BUCKET"
echo "  Cert ARN   : $CERT_ARN"
echo "  Region     : $AWS_REGION"
echo "  Namespace  : $NAMESPACE"
echo ""

# ─── Add Helm repositories ──────────────────────────────────────────
echo "Adding Helm repositories..."
helm repo add grafana https://grafana.github.io/helm-charts 2>/dev/null || true
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>/dev/null || true
helm repo add eks https://aws.github.io/eks-charts 2>/dev/null || true
helm repo add external-dns https://kubernetes-sigs.github.io/external-dns/ 2>/dev/null || true
helm repo update

# ─── Helper: deploy a Helm chart with envsubst-templated values ──────
deploy() {
  local name="$1" chart="$2" values_file="$3"
  shift 3

  echo "Deploying $name..."
  envsubst '$S3_BUCKET $AWS_REGION $CERT_ARN' < "$SCRIPT_DIR/values/$values_file" | \
    helm upgrade --install "$name" "$chart" \
      --namespace "$NAMESPACE" \
      --create-namespace \
      -f - \
      "$@" \
      --wait --timeout 5m
  echo "  Done."
}

# ─── 0. Ingress infrastructure ────────────────────────────────────────

# AWS Load Balancer Controller
echo "Deploying aws-load-balancer-controller..."
helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller \
  --namespace kube-system \
  --set clusterName="$CLUSTER_NAME" \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller \
  --set region="$AWS_REGION" \
  --set vpcId="$(aws ec2 describe-vpcs \
    --filters "Name=tag:project,Values=auto-monitoring-hackathon" \
    --query "Vpcs[0].VpcId" --output text \
    --region "$AWS_REGION" $PROFILE_FLAG)" \
  --wait --timeout 5m
echo "  Done."

# external-dns
echo "Deploying external-dns..."
helm upgrade --install external-dns external-dns/external-dns \
  --namespace kube-system \
  --set provider.name=aws \
  --set serviceAccount.create=false \
  --set serviceAccount.name=external-dns \
  --set "domainFilters[0]=subq-sandbox.com" \
  --set policy=sync \
  --set registry=txt \
  --set txtOwnerId=auto-monitoring \
  --set "env[0].name=AWS_DEFAULT_REGION" \
  --set "env[0].value=$AWS_REGION" \
  --set "managedRecordTypes[0]=A" \
  --set "managedRecordTypes[1]=CNAME" \
  --wait --timeout 5m
echo "  Done."

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

# ─── 5. RBAC for backend ServiceAccount ──────────────────────────────
echo "Applying RBAC for cs-backend (node-reader)..."
kubectl apply -f "$SCRIPT_DIR/rbac-node-reader.yaml"
echo "  Done."

# ─── 6. Ingress resources ────────────────────────────────────────────
echo "Applying ingress resources..."
envsubst '$CERT_ARN' < "$SCRIPT_DIR/ingress.yaml" | kubectl apply -f -
echo "  Done."

# ─── Done ────────────────────────────────────────────────────────────
echo ""
echo "All charts deployed successfully!"
echo ""
echo "Public URLs (may take 2-3 min for ALB + DNS):"
echo "  https://grafana.hack.subq-sandbox.com   (admin / changeme)"
echo ""
echo "Backend access via port-forward (cluster-internal only):"
echo "  kubectl port-forward -n $NAMESPACE svc/mimir-gateway 8080:80"
echo "  kubectl port-forward -n $NAMESPACE svc/loki 3100:3100"
echo "  kubectl port-forward -n $NAMESPACE svc/tempo 3200:3200"
echo "  kubectl port-forward -n $NAMESPACE svc/pyroscope 4040:4040"
echo ""
echo "Send OTLP telemetry to Alloy (external):"
echo "  https://otlp.hack.subq-sandbox.com/v1/metrics"
echo "  https://otlp.hack.subq-sandbox.com/v1/traces"
echo "  https://otlp.hack.subq-sandbox.com/v1/logs"
echo ""
echo "Send OTLP telemetry to Alloy (cluster-internal):"
echo "  gRPC: alloy.$NAMESPACE.svc.cluster.local:4317"
echo "  HTTP: alloy.$NAMESPACE.svc.cluster.local:4318"
echo "  Faro: alloy.$NAMESPACE.svc.cluster.local:12347"
echo ""
echo "Verify:"
echo "  kubectl get ingress -n $NAMESPACE"
echo "  kubectl get pods -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller"
echo "  kubectl get pods -n kube-system -l app.kubernetes.io/name=external-dns"
