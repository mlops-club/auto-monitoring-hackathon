#!/usr/bin/env bash
set -euo pipefail

#
# Generates a standalone kubeconfig for external collaborators.
# No AWS credentials required to USE the generated file.
#
# Prerequisites (admin only):
#   - AWS CLI configured with --profile subq-sandbox
#   - kubectl access to the cluster (via IAM)
#
# Usage:
#   bash infra/generate-kubeconfig.sh
#
# Distribute the generated file to collaborators. They just:
#   export KUBECONFIG=path/to/auto-monitoring-kubeconfig.yaml
#   kubectl get nodes
#

CLUSTER_NAME="auto-monitoring"
REGION="us-west-2"
PROFILE="subq-sandbox"
SECRET_NAME="external-admin-token"
SECRET_NS="kube-system"
OUTPUT_FILE="auto-monitoring-kubeconfig.yaml"

echo "--- Fetching cluster info from EKS..."
CLUSTER_INFO=$(aws eks describe-cluster \
    --name "$CLUSTER_NAME" \
    --region "$REGION" \
    --profile "$PROFILE" \
    --output json)

ENDPOINT=$(echo "$CLUSTER_INFO" | python3 -c "import sys,json; print(json.load(sys.stdin)['cluster']['endpoint'])")
CA_DATA=$(echo "$CLUSTER_INFO" | python3 -c "import sys,json; print(json.load(sys.stdin)['cluster']['certificateAuthority']['data'])")

echo "--- Fetching service account token from cluster..."
TOKEN=$(kubectl get secret "$SECRET_NAME" \
    -n "$SECRET_NS" \
    -o jsonpath='{.data.token}' | base64 -d)

echo "--- Writing kubeconfig to ${OUTPUT_FILE}..."
cat > "$OUTPUT_FILE" <<EOF
apiVersion: v1
kind: Config
current-context: ${CLUSTER_NAME}
clusters:
  - name: ${CLUSTER_NAME}
    cluster:
      server: ${ENDPOINT}
      certificate-authority-data: ${CA_DATA}
contexts:
  - name: ${CLUSTER_NAME}
    context:
      cluster: ${CLUSTER_NAME}
      user: external-admin
users:
  - name: external-admin
    user:
      token: ${TOKEN}
EOF

echo "--- Done! Distribute this file to collaborators:"
echo "    ${OUTPUT_FILE}"
echo ""
echo "Collaborators use it with:"
echo "    export KUBECONFIG=${OUTPUT_FILE}"
echo "    kubectl get nodes"
