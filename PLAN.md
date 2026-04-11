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

## Epic - Monitoring UI

### 1. Make loki, tempo, pyroscope, and mimir only accessible within the eks cluster

1. [ ] These services are exposed on the public internet. Make them private so they are no longer exposed publicly.
2. [ ] Validate that the services can be accessed via a portfoward using the `kubectl` CLI

### 2. Full-stack FastAPI app

1. [ ] Create a FastAPI app in `cluster-stats-ui/backend/src/cs_backend/`
   1. [ ] uses the `create_app()` pattern
   2. [ ] manages dependencies with `uv`
   3. [ ] manages settings with `pydantic-settings` and the settings dict
   4. [ ] Make it a proper package with an `src/` folder via `uv init`
   5. [ ] Has a `tests/` framework set up as in [this reference project](https://github.com/mlops-club/cloud-course-project/tree/main/tests)
      1. [ ] Local tests that mock everything without filling the code with stubs (think `moto`)
      2. [ ] Functional tests that point at external components, e.g. the database, AWS, other APIs, etc.
   6. [ ] Uses pydantic models to ensure OpenAPI docs are correct
   7. [ ] Uses proper HTTP verbs and nouns in all endpoints

2. [ ] Create a frontend application in `cluster-stats-ui/frontend/`
   1. [ ] Follow the pattern shown in [this repo](https://github.com/phitoduck/come-follow-me-app/tree/main/rs-frontend/src)
      1. [ ] use Vite, TypeScript, React
      2. [ ] have a `run` script that is used to bundle the backend and frontend, model the run script after [this one](https://raw.githubusercontent.com/mlops-club/cloud-course-project/refs/heads/main/run.sh?token=GHSAT0AAAAAADWR4ABULUA3QV72YK2PCCY22OZ5FIA)
         1. [ ] Do NOT use `poethepoet` or `just`, simply use a `run` bash script
         2. [ ] Put the `poethepoet` commands into the `run` script, use `uv` for all python processes
         3. [ ] Have a few `serve:<placeholder>` commands that serve the app in a few ways
            1. [ ] the frontend running separately from the backend using `pnpm run dev` or similar and backend running with `uv run`
            2. [ ] frontend built via a watch process that rebuilds on save and is served out of the backend (so the two are served together from the backend). Just do the boilerplate `vite` frontend for now. Initialize this using the `vite` CLI
   2. [ ] Verify all this by running the serving in both modes. 
      1. [ ] Control a chrome browser to interact with the UI to verify that it comes up on both serves and causes the backend to emit logs
      2. [ ] Edit frontend files and verify that the watchers rebundle it correctly for the `serve:<placeholder>` commands
      3. [ ] Add some basic `pytest` tests that validate that files are served when a request is made to the serving endpoint
      4. [ ] Create a new GitHub Actions workflow that executes these tests on PR open and pushed commits to an open PR branch; only run the tests when files related to the frontend/backend are changed

3. [ ] Convert the `docs/cluster-view.html` script to TypeScript/React and have it powered by queries to the FastAPI backend, which in turn query mimir metrics
   1. [ ] Have two local development modes: 
      1. [ ] run everything in docker-compose.yaml locally in a single stack: node exporter, alloy, fastapi with a volume mount that watches the frontend and backend directories for changes and triggers rebuilds
      2. [ ] run the bundled fastapi/react app and point it at the real mimir service in EKS using `kubectl` to portforward mimir (Amit does not believe this is possible, prove him wrong; Please I will be fired if I can't convince him 😭)
   2. [ ] Design and implement some playwright tests that rely on running the entire app and mimir, node exporter, fastapi stack in docker-compose with some sample data (or mock node exporter metrics if you can) and have playwright validate that certain things show up on screen
   3. [ ] Add to the github actions workflow this playwright test suite. Ensure that jobs that can be parallelized in the workflow are indeed parallelized.

4. [ ] Instrument FastAPI app with OTel following the patterns [shown here](https://github.com/mlops-club/cloud-course-project/tree/main/src/files_api/monitoring), but use the OTel SDKs, not AWS Xray
   1. [ ] Verify this by
      1. [ ] Generating a OTel trace id and send that to our FastAPI app in a request to ANY endpoint in the request header
         1. [ ] Verify that 
            1. [ ] a trace with the generated correlation ID ends up in tempo
            2. [ ] a log with the generated correlation ID ends up in loki
         2. [ ] Do this locally -- add a utility `run` command for these
            1. [ ] Run FastAPI and the grafana stack in docker-compose so we can see the metrics locally
            2. [ ] Use `kubectl` to portforward alloy and point a local fastapi instance at that
      2. [ ] TBD: plan a way to verify that metrics are showing up properly as well