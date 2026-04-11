# Changelog

## 2026-04-11 — K8s node labels API + metric-to-node mapping in Alloy

### Why

The monitoring dashboard needs to filter/group nodes by K8s labels (zone,
instance type, etc.) and join those labels to metric streams. Node-exporter
metrics only carried `instance=IP:port` — there was no way to correlate metrics
to K8s node names or their labels.

### What changed

#### 1. Alloy relabel rules (`infra/k8s/helm/values/alloy.yaml`)

Added `node` relabel rules to both `node_exporter` and `cadvisor` discovery
blocks so all scraped metrics carry the K8s node name. This enables joining
metrics to K8s API labels on node name.

- `node_exporter`: copies `__meta_kubernetes_pod_node_name` → `node`
- `cadvisor`: copies `__meta_kubernetes_node_name` → `node`

#### 2. K8s node labels endpoint (`cluster-stats-ui/backend/`)

- **New module `k8s.py`** — queries the K8s API (`list_node()`) for node labels
  with a 60-second TTL cache. Uses in-cluster config when deployed, falls back
  to `~/.kube/config` for local development.
- **New endpoint `GET /api/labels`** — returns
  `{nodes: {node_name: {label_key: label_value}}}` for populating filter
  dropdowns in the UI.
- **New schema `NodeLabelsResponse`** — Pydantic model with OpenAPI examples.
- **New dependency `kubernetes`** — Python client for K8s API access.
- **Settings update** — changed `mimir_base_url` default from `localhost:9090`
  to `http://mimir:8080` to match the in-cluster Mimir service.

#### 3. RBAC for backend ServiceAccount (`infra/k8s/helm/rbac-node-reader.yaml`)

New ClusterRole + ClusterRoleBinding granting the `cs-backend` ServiceAccount
`get`/`list` access to nodes. Applied via the deploy script.

#### 4. Deploy script update (`infra/k8s/helm/deploy-monitoring.sh`)

Added `kubectl apply` step for the RBAC manifest before ingress resources.

### How it was verified

- All 9 existing backend unit tests pass.
- `GET /api/labels` returns correct node labels for both EKS nodes, matching
  `kubectl get nodes --show-labels` output (instance type, AZ, capacity type,
  etc.).
- Verified via `curl http://localhost:3000/api/labels` and the interactive
  `/docs` Swagger UI.

## 2026-04-11 — Cluster Stats UI frontend scaffold and local run flows

### Why

The backend scaffold was in place, but the monitoring UI still had no frontend,
no shared local run entrypoint, and no way to verify frontend/backend serving
behavior together before the real mimir-backed features land.

### What changed

#### 1. Frontend app (`cluster-stats-ui/frontend/`)

Added a Vite + React + TypeScript application following the requested pattern:

- **Vite/React/TypeScript scaffold** — committed as a standalone frontend app
  managed with `pnpm`.
- **Split-mode development** — Vite serves the frontend directly and proxies
  `/health`, `/openapi.json`, and `/api/*` requests to the backend.
- **Bundled-mode development** — Vite builds into
  `cluster-stats-ui/backend/src/cs_backend/static/` so FastAPI can serve the
  frontend and SPA routes from one process.
- **Placeholder UI shell** — includes route handling and a backend probe button
  so frontend/backend integration can be exercised before real cluster data is
  wired in.

#### 2. Shared run script (`cluster-stats-ui/run`)

Added a bash `run` entrypoint to manage local workflows without `poethepoet` or
`just`:

- **Install commands** — `install:frontend`, `install:backend`
- **Build commands** — `build:frontend`, `build:frontend:watch`
- **Serve commands** — `serve:frontend`, `serve:backend`, `serve:split`,
  `serve:bundled`, `serve:bundled-watch`
- **Test commands** — `test:backend`, `test:static`

Python processes run via `uv`, matching the repo conventions.

#### 3. Backend follow-up for frontend serving (`cluster-stats-ui/backend/`)

Extended the merged backend scaffold so it can support the frontend workflow:

- **Static asset serving** — serves the built frontend bundle from
  `src/cs_backend/static/`
- **SPA fallback** — returns `index.html` for client-side routes like
  `/clusters/demo`
- **UI probe endpoint** — `GET /api/ui-probe` emits backend logs and returns a
  small JSON response for frontend verification
- **Test fixture updates** — backend tests now mount temporary static assets so
  serving behavior is covered in-process

#### 4. Workflow expansion (`.github/workflows/cluster-stats-ui.yml`)

Expanded the Cluster Stats UI workflow so PRs touching either the frontend or
backend run the relevant checks:

- **`frontend-build`** — installs `pnpm` deps and runs the frontend build
- **`backend-unit-tests`** — runs backend unit tests
- **`backend-functional-tests`** — builds the frontend bundle, starts the
  backend, and runs backend functional tests against the live server

### How it was verified

- `./run install:frontend`
- `./run install:backend`
- `./run build:frontend`
- `./run test:backend`
- `./run test:static`
- `pnpm run lint` in `cluster-stats-ui/frontend`
- Verified `serve:frontend`, `serve:backend`, `serve:split`, `serve:bundled`,
  `build:frontend:watch`, and `serve:bundled-watch`
- Used headless Chromium to load the split-mode UI, click the probe button, and
  observe the backend log emission
- Edited frontend files while both watch modes were running and confirmed the
  bundle/HMR updated correctly

## 2026-04-11 — Cluster Stats UI backend and CI workflow

### Why

The monitoring UI needs a FastAPI backend to serve cluster metrics. This sets up
the backend application scaffolding with a proper test framework and a GitHub
Actions workflow so tests run automatically on every PR.

### What changed

#### 1. FastAPI backend (`cluster-stats-ui/backend/`)

New `uv`-managed Python package at `cluster-stats-ui/backend/src/cs_backend/`
following the same patterns as `apigw-rest-api/`:

- **`create_app()` factory** — settings-injectable, no globals. Settings stored
  on `app.state` and accessed via `Depends(get_settings)`.
- **`pydantic-settings`** — `Settings` class with env-driven config
  (`APP_NAME`, `DEBUG`, `MIMIR_BASE_URL`).
- **Pydantic response models** — `HealthResponse` and `ErrorResponse` with
  `Field(...)` descriptions and `json_schema_extra` examples for OpenAPI docs.
- **Global error handler** — catches unhandled exceptions, returns structured JSON.
- **Proper HTTP verbs/nouns** — `GET /health` endpoint to start.

#### 2. Test framework (`cluster-stats-ui/backend/tests/`)

- **Fixtures as plugins** — `tests/fixtures/` modules registered via
  `pytest_plugins` in `conftest.py` (same pattern as cloud-course-project).
- **Unit tests** (`tests/unit_tests/`) — 5 tests using `FastAPI.TestClient`,
  fully in-process, no external dependencies.
- **Functional tests** (`tests/functional_tests/`) — uses `httpx.Client` against
  a live server via `CS_BACKEND_BASE_URL` env var, marked `@slow`.

#### 3. GitHub Actions workflow (`.github/workflows/cluster-stats-ui.yml`)

Triggers on PRs and pushes to main when `cluster-stats-ui/**` files change.
Two jobs run **in parallel**:

- **`backend-unit-tests`** — installs deps, runs unit tests with coverage.
- **`backend-functional-tests`** — starts the server in background, waits for
  health, runs functional tests against it.

### How it was verified

- All 5 unit tests pass locally (`uv run pytest tests/unit_tests/ -v`).
- Functional test properly deselected with `-m "not slow"`.
- CI workflow validated by pushing to PR branch.

## 2026-04-11 — Make monitoring backends cluster-internal only

### Why

Loki, Tempo, Pyroscope, and Mimir were exposed on the public internet via the
shared ALB. These are backend storage services that should only be accessed by
Grafana and Alloy within the EKS cluster — there is no reason for them to be
publicly reachable.

### What changed

#### 1. Removed public Ingress resources (`infra/k8s/helm/ingress.yaml`)

Deleted the four ALB Ingress resources for Mimir, Loki, Tempo, and Pyroscope.
Only Grafana and Alloy OTLP ingresses remain on the internet-facing ALB. The
underlying Kubernetes Services are ClusterIP (Helm defaults), so they remain
reachable within the cluster at their usual addresses:

- `loki.monitoring.svc.cluster.local:3100`
- `tempo.monitoring.svc.cluster.local:3200`
- `pyroscope.monitoring.svc.cluster.local:4040`
- `mimir-gateway.monitoring.svc.cluster.local:80`

#### 2. Updated deploy script output (`infra/k8s/helm/deploy-monitoring.sh`)

Replaced the four public URL lines with `kubectl port-forward` commands showing
how to access the backends locally for debugging.

### How it was verified

- Helm workflow dispatch deployed successfully from branch `stormy-composer`
- `kubectl get ingress -n monitoring` shows only `grafana` and `alloy-otlp`
- Grafana remains accessible at `https://grafana.hack.subq-sandbox.com`
- DNS cleanup handled automatically by external-dns (`policy=sync`)

## 2026-04-11 — CI/CD for CDK and Helm Deployments

### Why

CDK and Helm deployments were manual. We needed GitHub Actions workflows to
automate infrastructure provisioning and Helm chart deploys on push to main,
plus helm-diff comments on PRs so reviewers can see what will change.

### What changed

#### 1. GitHub Actions workflows

- **`cdk.yml`** — runs `cdk diff` on PRs and `cdk deploy` on push to main.
  Uses a reusable `aws-eks-auth` action for AWS/EKS authentication.
- **`helm.yml`** — runs `helm diff` on PRs (posts a comment with the diff) and
  `helm deploy` on push to main via the existing `deploy-monitoring.sh` script.

#### 2. Reusable AWS + EKS auth action (`.github/actions/aws-eks-auth`)

Composite action that assumes an IAM role via OIDC, then assumes the EKS
masters role and updates kubeconfig. Used by both workflows.

#### 3. IAM / CDK fixes (`infra/infra.py`, `infra/github-oidc-stack.py`)

- Granted `sts:TagSession` on MastersRole for GitHub Actions role chaining.
- Granted `eks:DescribeCluster` to MastersRole for kubeconfig setup.
- Used `--role-arn` in kubeconfig instead of role chaining (avoids a double
  assume-role that was failing in CI).

#### 4. Helm-diff plugin install fix (`.github/workflows/helm.yml`)

The original `helm plugin install ... || true` silently swallowed failures.
Newer Helm versions also require `--verify=false` for git-sourced plugins.
Fixed to use `--verify=false`, fall back to `helm plugin update`, and verify
with `helm diff version`.

#### 5. setup-uv cache disabled (`cdk.yml`)

Disabled uv cache since the repo has no `uv.lock` file, which was causing
cache restore failures.

### How it was verified

All CI checks passed on PR #3. The helm-diff PR comment now shows actual diff
output (previously showed "unknown command diff" errors). CDK workflow runs
successfully.

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
