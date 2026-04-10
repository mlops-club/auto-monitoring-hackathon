# CloudWatch Metric Streams → Grafana Stack

> Status: Reference guide (not yet deployed)

## Overview

CloudWatch Metric Streams push metrics from AWS accounts into a Kinesis
Firehose, which delivers them to an HTTP endpoint. Our Alloy collector already
accepts OTLP HTTP at `https://otlp.hack.subq-sandbox.com`, so the pipeline is:

```
CloudWatch Metric Stream
        ↓ (push, ~2-3 min latency)
Kinesis Firehose
        ↓ (OTLP HTTP delivery)
https://otlp.hack.subq-sandbox.com/v1/metrics
        ↓
Alloy → Mimir
```

## Why Metric Streams instead of a pull-based exporter

| Concern | Pull (e.g. YACE) | Push (Metric Streams) |
|---|---|---|
| Cross-account | IAM role chaining per account, central config grows | Each account runs its own stream to the same endpoint |
| Latency | 5 min polling floor | ~2-3 min |
| Metric selection | Fine-grained per metric name | Namespace-level (all of `AWS/RDS` or none) |
| Idle cost | Zero | Stream + Firehose still run |
| Scaling | API costs grow with metric count x frequency | Fixed Firehose cost per GB delivered |

Metric Streams are the better fit when you have multiple AWS accounts or want
near-real-time delivery without managing polling infrastructure.

## CDK script

The file `infra/metric-streams-stack.py` is a self-contained AWS CDK script
that deploys a Metric Stream + Firehose pair in any account. It is independent
of the main `infra/infra.py` stack and can be deployed separately.

### Usage

```bash
# Deploy in the current account (streams RDS, API Gateway, Lambda metrics)
npx cdk deploy --app "uv run infra/metric-streams-stack.py" --profile <your-profile>

# Deploy in a different account (e.g. for cross-account RDS)
npx cdk deploy --app "uv run infra/metric-streams-stack.py" --profile <other-account-profile>
```

### What it creates

1. **Kinesis Firehose** — HTTP endpoint delivery stream targeting the OTLP
   ingress. Backs up failed records to an S3 bucket.
2. **CloudWatch Metric Stream** — filters to `AWS/RDS`, `AWS/ApiGateway`, and
   `AWS/Lambda` namespaces. Outputs in OpenTelemetry 0.7 format (native OTLP).
3. **IAM roles** — least-privilege roles for Firehose (S3 write, HTTP delivery)
   and Metric Stream (Firehose put).
4. **S3 backup bucket** — catches any records Firehose fails to deliver.

### Customizing

- **Add namespaces**: append to the `include_filters` list in the script (e.g.
  `"AWS/ECS"`, `"AWS/SQS"`).
- **Stream all metrics**: remove the `include_filter` blocks entirely.
  Warning: this can be expensive in accounts with many services.
- **Change target endpoint**: update `OTLP_ENDPOINT` at the top of the script.
- **CloudWatch Logs**: Metric Streams handle metrics only. For logs, create a
  CloudWatch Logs subscription filter → Firehose → same OTLP endpoint with
  `/v1/logs` path. This is a separate pipeline not covered by this script.

### Costs

- **Metric Stream**: $0.003 per 1,000 metric updates
- **Firehose**: $0.029 per GB delivered
- **S3 backup**: standard S3 pricing (only for failed deliveries)

For a typical small account with ~200 RDS + APIGW + Lambda metrics updating
every 60 seconds, expect roughly $25-50/month.
