# External Access Plan: Ingesting & Querying Telemetry from Outside EKS

> Status: Implemented (steps 1-3); steps 4-6 require external/runtime changes
> Date: 2026-04-10

## Goal

Enable services running **outside** the EKS cluster (RDS, API Gateway, Lambda, etc.) to:

1. **Query** metrics, logs, and traces from the observability backends
2. **Send** metrics, logs, and traces into the observability backends

## Current State

| Capability | Status |
|---|---|
| Query backends externally | Partial — Mimir/Loki/Tempo/Pyroscope ingresses exist, but **no auth** |
| Send telemetry from outside EKS | **Done** — Alloy OTLP ingress at `otlp.hack.subq-sandbox.com` |
| RDS metrics/logs | **Not yet** — Metric Streams guide + CDK script ready, not deployed |
| API Gateway / Lambda / FastAPI | **Ingest path ready** — OTLP endpoint exposed; Lambda OTEL layer config documented |

### External Endpoints (unauthenticated)

- `https://grafana.hack.subq-sandbox.com/` — Dashboards
- `https://mimir.hack.subq-sandbox.com/` — Metrics API
- `https://loki.hack.subq-sandbox.com/` — Logs API
- `https://tempo.hack.subq-sandbox.com/` — Traces API
- `https://pyroscope.hack.subq-sandbox.com/` — Profiles API
- `https://otlp.hack.subq-sandbox.com/` — OTLP ingest (write plane) **NEW**

---

## Plan

### 1. Expose Alloy OTLP Endpoint Externally ✅

Add an ingress for Alloy's OTLP HTTP port (4318) so that external services have a single
endpoint to push metrics, logs, and traces.

**New endpoint:** `https://otlp.hack.subq-sandbox.com`

Write paths:
- `https://otlp.hack.subq-sandbox.com/v1/metrics`
- `https://otlp.hack.subq-sandbox.com/v1/traces`
- `https://otlp.hack.subq-sandbox.com/v1/logs`

**Change:** Add ingress resource to `infra/k8s/helm/ingress.yaml`:

```yaml
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: alloy-otlp
  namespace: monitoring
  annotations:
    alb.ingress.kubernetes.io/group.name: monitoring
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTPS": 443}]'
    alb.ingress.kubernetes.io/certificate-arn: ${CERT_ARN}
    alb.ingress.kubernetes.io/healthcheck-path: /ready
    external-dns.alpha.kubernetes.io/hostname: otlp.hack.subq-sandbox.com
spec:
  ingressClassName: alb
  rules:
    - host: otlp.hack.subq-sandbox.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: alloy
                port:
                  number: 4318
```

### 2. Ingest CloudWatch Metrics via Metric Streams (future)

CloudWatch metrics (RDS, API Gateway, Lambda, etc.) will be ingested using
**CloudWatch Metric Streams** — a push-based pipeline that delivers metrics
through Kinesis Firehose to the OTLP endpoint exposed in step 1.

**Architecture:** CloudWatch Metric Stream → Kinesis Firehose → `https://otlp.hack.subq-sandbox.com/v1/metrics` → Alloy → Mimir

This approach was chosen over pull-based exporters (e.g. YACE) because it
scales across multiple AWS accounts without central config changes and provides
near-real-time (~2-3 min) delivery.

**Reference:**
- `docs/metric-streams-guide.md` — full guide with tradeoffs and cost estimates
- `infra/metric-streams-stack.py` — self-contained CDK script, deploy in any account

### 3. Add IRSA to Alloy Service Account ✅

Alloy currently has no IAM role. CloudWatch scraping requires AWS API access.

**Change:** In `infra/infra.py`, create an IRSA-backed service account for Alloy with these permissions:

- `cloudwatch:GetMetricData`
- `cloudwatch:ListMetrics`
- `logs:DescribeLogGroups`
- `logs:FilterLogEvents`
- `logs:GetLogEvents`

Follow the same pattern used for `mimir`, `loki`, `tempo`, and `pyroscope` service accounts.

### 4. Configure Lambda OTEL Layer for FastAPI

Use the AWS Distro for OpenTelemetry (ADOT) Lambda layer so the FastAPI app sends traces,
metrics, and logs directly to the Alloy OTLP endpoint.

**Lambda environment variables:**

```
OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp.hack.subq-sandbox.com
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_SERVICE_NAME=my-fastapi-app
```

The OTEL SDK in FastAPI will send:
- Traces → Alloy → Tempo
- Metrics → Alloy → Mimir
- Logs → Alloy → Loki

### 5. Drop X-Ray in Favor of Native OTEL

X-Ray is redundant when using the OTEL SDK directly. Bridging X-Ray into Tempo adds
complexity with no benefit.

**Changes:**
- Disable X-Ray active tracing on API Gateway and Lambda
- Rely on OTEL SDK + ADOT Lambda layer for all trace collection
- Use W3C Trace Context propagation (OTEL default) instead of X-Ray headers

### 6. Add Authentication to External Endpoints

All current ingresses are unauthenticated. Before wiring up external producers/consumers,
add auth.

**Options (pick one per plane):**

**Write plane (OTLP ingest):**
- API key header check — add `otelcol.auth.headers` in Alloy config to validate a
  shared secret in the `Authorization` header
- ALB Lambda authorizer — validate a bearer token at the ALB layer

**Read plane (query APIs):**
- ALB + Cognito — attach a Cognito user pool to the ALB listener rules for
  Mimir/Loki/Tempo/Pyroscope ingresses
- ALB + OIDC — use an external IdP (Google, Okta, etc.)
- Restrict to internal — change `scheme: internet-facing` to `scheme: internal` and
  use VPC peering or PrivateLink for access

---

## Signal Flow Summary

| Signal | Source | Path to Stack |
|---|---|---|
| RDS metrics | CloudWatch | (future) Metric Stream → Firehose → OTLP → Alloy → Mimir |
| RDS logs (slow query, error) | CloudWatch Logs | (future) Subscription filter → Firehose → OTLP → Alloy → Loki |
| APIGW access logs | CloudWatch Logs | (future) Subscription filter → Firehose → OTLP → Alloy → Loki |
| APIGW metrics (count, latency) | CloudWatch | (future) Metric Stream → Firehose → OTLP → Alloy → Mimir |
| Lambda metrics (invocations, errors) | CloudWatch | (future) Metric Stream → Firehose → OTLP → Alloy → Mimir |
| FastAPI logs | OTEL SDK in Lambda | OTLP HTTP → Alloy → Loki |
| FastAPI traces | OTEL SDK in Lambda | OTLP HTTP → Alloy → Tempo |
| FastAPI metrics | OTEL SDK in Lambda | OTLP HTTP → Alloy → Mimir |

## Priority Order

1. ~~**Expose Alloy OTLP ingress** — unlocks all external write paths~~ ✅ Done
2. ~~**Add IRSA to Alloy** — prerequisite for CloudWatch + Metric Streams~~ ✅ Done
3. **Deploy Metric Streams** — CDK script ready (`infra/metric-streams-stack.py`), deploy when needed
4. **Configure Lambda OTEL layer** — gets FastAPI telemetry flowing (runtime config, env vars documented in step 4)
5. **Drop X-Ray** — simplify to a single tracing system (AWS console changes)
6. **Add auth to all external endpoints** — secure before production use
