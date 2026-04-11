## Epic - Grafana Stack on EKS

1. [x] Make sure EKS cluster exposes the grafana stack at `*.hack.subq-sandbox.com`
2. [ ] Make sure metrics, logs, and traces can be sent to the grafana stack from outside the cluster

## Epic - Continuous Delivery

1. [x] Create a GitHub actions workflow that
   1. [x] Deploys the AWS CDK infra to the appropriate account
   2. [x] Deploys the helm charts to the cluster in the account
   3. [x] Only runs [1] if cdk-related code changed
   4. [x] Only runs [2] if helm/k8s-related code changed
2. [x] Set up the AWS OIDC connection with GitHub via IaC
   1. [x] Delegate access to the repo to deploy to the region

Use the `gh` CLI for operations against the repo to configure it.

## Epic - Collaboration

Vague goal: figure out how to get everyone the AWS, EKS, and Grafana stack access they need.

## Epic - Ingest Telemetry

### 2.a - Local script

1. [ ] Write a bash script at `otel/script/` that invokes a python script via `uv`
2. [ ] Traces
   1. [ ] Have the script use the `httpx` library to make a request to a web page
   2. [ ] Use autoinstrumentation to track trace information in the request
   3. [ ] Set the Otel variables in the bash script to configure the `service.name`, OTel backend, etc.
   4. [ ] Validate that the trace made it into tempo backend
3. [ ] Metrics
   1. [ ] Instrument the FastAPI app to emit a custom counter
   2. [ ] Collect that metric and emit it to the Otel backend
   3. [ ] Validate that the metric made it to the mimir backend
4. [ ] Logs
   1. [ ] Emit logs in the python script via `structlog`
   2. [ ] Inject the Otel trace and span information into the log statements via autoinstrumentation
   3. [ ] Include some relevant key-value pairs in the structured log
   4. [ ] Collect the log and emit it to the logs backend
   5. [ ] Validate that the log made it to the loki backend

### 2.b - OSS docker container from docker hub or elsewhere

### 2.c - Custom, dockerized FastAPI app running locally

1. [ ] Create a FastAPI app that has a 
   1. [ ] uses the `create_app()` pattern
   2. [ ] manages dependencies with `uv`
   3. [ ] manages settings with `pydantic-settings` and the settings dict
   4. [ ] Make it a proper package with an `src/` folder via `uv init`
   5. [ ] Has a `tests/` framework set up as in [this reference project](https://github.com/mlops-club/cloud-course-project/tree/main/tests)
      1. [ ] Local tests that mock everything without filling the code with stubs (think `moto`)
      2. [ ] Functional tests that point at external components, e.g. the database, AWS, other APIs, etc.
   6. [ ] Uses pydantic models to ensure OpenAPI docs are correct
   7. [ ] Uses proper HTTP verbs and nouns in all endpoints
2. [ ] Instrument with OTel following the patterns [shown here](https://github.com/mlops-club/cloud-course-project/tree/main/src/files_api/monitoring), but use the OTel SDKs, not AWS Xray

### 2.d - Custom, dockerized FastAPI app deployed to EKS

### 2.e - Local FastAPI that sends metrics to the EKS grafana stack