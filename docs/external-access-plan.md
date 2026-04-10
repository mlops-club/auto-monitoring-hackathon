# External Access Plan: Ingesting & Querying Telemetry from Outside EKS

> Status: Draft
> Date: 2026-04-10

## Goal

Enable services running **outside** the EKS cluster (RDS, API Gateway, Lambda, etc.) to:

1. **Query** metrics, logs, and traces from the observability backends
2. **Send** metrics, logs, and traces into the observability backends

## Current State

| Capability | Status |
|---|---|
| Query backends externally | Partial — Mimir/Loki/Tempo/Pyroscope ingresses exist, but **no auth** |
| Send telemetry from outside EKS | **Not working** — Alloy (OTLP receiver) has no ingress |
| RDS metrics/logs | Not wired up |
| API Gateway / Lambda / FastAPI | No external ingest path |

### Existing External Endpoints (unauthenticated)

- `https://grafana.hack.subq-sandbox.com/` — Dashboards
- `https://mimir.hack.subq-sandbox.com/` — Metrics API
- `https://loki.hack.subq-sandbox.com/` — Logs API
- `https://tempo.hack.subq-sandbox.com/` — Traces API
- `https://pyroscope.hack.subq-sandbox.com/` — Profiles API

---

## Plan

### 1. Expose Alloy OTLP Endpoint Externally

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

### 2. Add CloudWatch Scraping to Alloy

Alloy can pull metrics and logs from CloudWatch, covering RDS and API Gateway signals
that can't push telemetry directly.

**Change:** Add to `infra/k8s/helm/values/alloy.yaml` configMap:

```river
// RDS CloudWatch Metrics
prometheus.exporter.cloudwatch "rds" {
  sts_region = "us-west-2"
  discovery {
    type    = "AWS/RDS"
    regions = ["us-west-2"]
    metrics {
      name       = ["CPUUtilization", "DatabaseConnections", "FreeableMemory",
                     "ReadIOPS", "WriteIOPS", "ReadLatency", "WriteLatency",
                     "FreeStorageSpace", "DiskQueueDepth"]
      period     = 300
      statistics = ["Average"]
    }
  }
}
prometheus.scrape "rds_cloudwatch" {
  targets    = prometheus.exporter.cloudwatch.rds.targets
  forward_to = [prometheus.remote_write.mimir.receiver]
}

// API Gateway CloudWatch Metrics
prometheus.exporter.cloudwatch "apigw" {
  sts_region = "us-west-2"
  discovery {
    type    = "AWS/ApiGateway"
    regions = ["us-west-2"]
    metrics {
      name       = ["Count", "Latency", "IntegrationLatency", "4XXError", "5XXError"]
      period     = 300
      statistics = ["Sum", "Average"]
    }
  }
}
prometheus.scrape "apigw_cloudwatch" {
  targets    = prometheus.exporter.cloudwatch.apigw.targets
  forward_to = [prometheus.remote_write.mimir.receiver]
}

// RDS + APIGW + Lambda Logs from CloudWatch Logs
loki.source.cloudwatch "aws_logs" {
  region                = "us-west-2"
  log_group_name_prefix = "/aws/rds/"
  forward_to            = [loki.write.default.receiver]
}
loki.source.cloudwatch "apigw_logs" {
  region                = "us-west-2"
  log_group_name_prefix = "/aws/apigateway/"
  forward_to            = [loki.write.default.receiver]
}
loki.source.cloudwatch "lambda_logs" {
  region                = "us-west-2"
  log_group_name_prefix = "/aws/lambda/"
  forward_to            = [loki.write.default.receiver]
}
```

### 3. Add IRSA to Alloy Service Account

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
| RDS metrics | CloudWatch | Alloy `cloudwatch` exporter → Mimir |
| RDS logs (slow query, error) | CloudWatch Logs | Alloy `loki.source.cloudwatch` → Loki |
| APIGW access logs | CloudWatch Logs | Alloy `loki.source.cloudwatch` → Loki |
| APIGW metrics (count, latency) | CloudWatch | Alloy `cloudwatch` exporter → Mimir |
| FastAPI logs | OTEL SDK in Lambda | OTLP HTTP → Alloy → Loki |
| FastAPI traces | OTEL SDK in Lambda | OTLP HTTP → Alloy → Tempo |
| FastAPI metrics | OTEL SDK in Lambda | OTLP HTTP → Alloy → Mimir |

## Priority Order

1. **Expose Alloy OTLP ingress** — unlocks all external write paths
2. **Add IRSA to Alloy** — prerequisite for CloudWatch scraping
3. **Add CloudWatch scraping to Alloy** — gets RDS and APIGW signals flowing
4. **Configure Lambda OTEL layer** — gets FastAPI telemetry flowing
5. **Drop X-Ray** — simplify to a single tracing system
6. **Add auth to all external endpoints** — secure before production use
