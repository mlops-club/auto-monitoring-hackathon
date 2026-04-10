# Changelog

## 2026-04-10 — External OTLP Ingress, Alloy IRSA, and Metric Streams Guide

### Why

Services running outside the EKS cluster (Lambda, API Gateway, RDS) had no way
to send telemetry into the observability stack. The Alloy collector also lacked
an IAM role, blocking any future AWS API integration. This change exposes the
OTLP write endpoint externally, sets up Alloy with an IRSA-backed service
account, and documents the path for ingesting CloudWatch metrics via Metric
Streams when we're ready.

### What changed

#### 1. External OTLP endpoint (`infra/k8s/helm/ingress.yaml`)

Added an ALB ingress for `otlp.hack.subq-sandbox.com` that routes to Alloy's
OTLP HTTP receiver on port 4318. Any service outside the cluster can now push
metrics, traces, and logs over OTLP HTTP:

- `POST /v1/metrics`
- `POST /v1/traces`
- `POST /v1/logs`

The ingress shares the existing ALB group (`monitoring`), wildcard TLS
certificate, and external-dns annotations so it gets a Route 53 A record
automatically.

#### 2. IRSA for Alloy (`infra/infra.py`)

Created an IRSA-backed Kubernetes service account named `alloy` in the
`monitoring` namespace. The associated IAM role grants permissions needed for
future CloudWatch integration and Metric Streams:

- **CloudWatch**: `GetMetricData`, `GetMetricStatistics`, `ListMetrics`
- **Resource discovery**: `tag:GetResources`, `iam:ListAccountAliases`
- **Service-specific describe**: `rds:Describe*`, `apigateway:GET`,
  `lambda:ListFunctions`, `lambda:ListTags`
- **CloudWatch Logs**: `logs:DescribeLogGroups`, `logs:FilterLogEvents`,
  `logs:GetLogEvents`

A new CloudFormation output `AlloyRoleArn` is emitted so the deploy script can
validate its presence.

#### 3. Alloy switched to IRSA service account (`infra/k8s/helm/values/alloy.yaml`)

Changed `serviceAccount.create` from `true` to `false` and set
`serviceAccount.name: alloy` so the Helm chart uses the CDK-managed IRSA
service account instead of creating its own. This is the same pattern used by
mimir, loki, tempo, and pyroscope.

#### 4. Deploy script updates (`infra/k8s/helm/deploy-monitoring.sh`)

- Fetches and validates the new `AlloyRoleArn` CloudFormation output.
- Prints the external OTLP URLs in the post-deploy summary.

#### 5. CloudWatch Metric Streams guide and CDK script (new files)

We evaluated pull-based CloudWatch scraping (YACE) but decided against it.
Metric Streams are a better fit because they scale across multiple AWS accounts
(each account runs its own stream pointing at the same OTLP endpoint) and
provide near-real-time delivery (~2-3 min) without managing polling
infrastructure. This matters for cross-account scenarios like monitoring an RDS
instance in a different AWS account.

Two new reference files for when we're ready to deploy:

- `docs/metric-streams-guide.md` — explains the architecture, tradeoffs vs
  pull-based exporters, customization options, and cost estimates.
- `infra/metric-streams-stack.py` — self-contained CDK script that deploys a
  CloudWatch Metric Stream + Kinesis Firehose pair in any AWS account, pushing
  metrics to the OTLP endpoint in OpenTelemetry 0.7 format. Configured for
  `AWS/RDS`, `AWS/ApiGateway`, and `AWS/Lambda` namespaces with p50/p99
  percentile statistics for latency metrics.

#### 6. Plan document updated (`docs/external-access-plan.md`)

- Status reflects that steps 1 (OTLP ingress) and 3 (IRSA) are done.
- CloudWatch scraping updated from YACE to Metric Streams as the planned path.
- Signal flow summary updated to show the future Metric Streams pipeline.

### How it was verified

**CDK deploy** succeeded after deleting the pre-existing `alloy` service
account that Helm had previously created (CDK cannot adopt an existing
resource). IAM policy was iteratively expanded after observing permission errors
during testing.

**Helm deploy** completed with all charts reporting `deployed`. The new
`alloy-otlp` ingress was created and assigned to the shared ALB.

**Pods**: all pods in the `monitoring` namespace running and healthy.

**DNS**: `dig otlp.hack.subq-sandbox.com` resolves to the ALB IPs (external-dns
created the A record).

**OTLP write paths**: tested with `curl` — all three endpoints return HTTP 200
with `{"partialSuccess":{}}`:

```
curl -X POST https://otlp.hack.subq-sandbox.com/v1/traces  -H "Content-Type: application/json" -d '{"resourceSpans":[]}'
curl -X POST https://otlp.hack.subq-sandbox.com/v1/metrics -H "Content-Type: application/json" -d '{"resourceMetrics":[]}'
curl -X POST https://otlp.hack.subq-sandbox.com/v1/logs    -H "Content-Type: application/json" -d '{"resourceLogs":[]}'
```

A test trace with `service.name=test-external` was also sent and accepted.

**IRSA**: `kubectl get sa alloy -n monitoring` shows the
`eks.amazonaws.com/role-arn` annotation pointing to the correct IAM role.

### Not yet deployed

- **CloudWatch Metric Streams** — guide and CDK script are ready; deploy when
  we need CloudWatch metrics flowing into Mimir.
- **CloudWatch Logs forwarding** — requires a subscription filter pipeline
  (Firehose → OTLP `/v1/logs`). Not yet scripted.
- **Lambda OTEL layer** — environment variables are documented in the plan but
  not yet applied to any Lambda function.
- **X-Ray removal** — requires AWS console / IaC changes to disable active
  tracing on API Gateway and Lambda.
- **Authentication** — all external endpoints (including the new OTLP ingress)
  are currently unauthenticated.
