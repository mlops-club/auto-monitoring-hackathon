# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "aws-cdk-lib>=2.180.0",
#     "constructs>=10.0.0",
# ]
# ///
"""
Hello API – APIGW + Lambda with ADOT OTel Collector (self-contained CDK script)

The ADOT collector Lambda layer runs as an extension alongside the function,
receives OTel data from the Python SDK on localhost:4318, and forwards it to
the Grafana stack at otlp.hack.subq-sandbox.com.

Deploy:
    npx cdk deploy --app "uv run apigw-rest-api/infra.py" --profile subq-sandbox

Destroy:
    npx cdk destroy --app "uv run apigw-rest-api/infra.py" --profile subq-sandbox
"""

import hashlib
import json
import os
from pathlib import Path

import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_apigateway as apigw,
    aws_lambda as _lambda,
    aws_logs as logs,
)
from constructs import Construct

THIS_DIR = Path(__file__).parent

OTLP_ENDPOINT = "https://otlp.hack.subq-sandbox.com"
SERVICE_NAME = "hello-api"

ENV = cdk.Environment(account="292783887127", region="us-west-2")

# ADOT collector Lambda layer (ARM64, us-west-2)
# https://aws-otel.github.io/docs/getting-started/lambda
ADOT_COLLECTOR_LAYER_ARN = (
    "arn:aws:lambda:us-west-2:901920570463:layer:aws-otel-collector-arm64-ver-0-117-0:1"
)

_ASSETS_TO_EXCLUDE: list[str] = [
    "tests/*",
    "docs/*",
    ".vscode",
    "*.env",
    ".venv",
    "*.pyc",
    "__pycache__",
    "*cache*",
    ".DS_Store",
    ".git",
    ".github",
    "infra.py",
]


class HelloApiStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- Lambda Layer (Python dependencies) ---
        layer = _lambda.LayerVersion(
            self,
            "HelloApiLayer",
            layer_version_name="hello-api-deps",
            description="Python dependencies for Hello API",
            compatible_architectures=[_lambda.Architecture.ARM_64],
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12],
            code=_lambda.Code.from_asset(
                path=THIS_DIR.as_posix(),
                deploy_time=True,
                asset_hash_type=cdk.AssetHashType.CUSTOM,
                asset_hash=hashlib.sha256(
                    (THIS_DIR / "pyproject.toml").read_bytes()
                    + (THIS_DIR / "uv.lock").read_bytes()
                ).hexdigest(),
                bundling=cdk.BundlingOptions(
                    image=_lambda.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash",
                        "-c",
                        "pip install --upgrade pip && "
                        "pip install uv && "
                        "uv pip install --no-cache --link-mode=copy "
                        "--requirements pyproject.toml --group aws-lambda "
                        "--target /asset-output/python",
                    ],
                    user="root",
                ),
                exclude=_ASSETS_TO_EXCLUDE,
            ),
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        # --- ADOT Collector Extension Layer ---
        adot_layer = _lambda.LayerVersion.from_layer_version_arn(
            self,
            "AdotCollectorLayer",
            layer_version_arn=ADOT_COLLECTOR_LAYER_ARN,
        )

        # --- CloudWatch Log Group ---
        log_group = logs.LogGroup(
            self,
            "HelloApiLogGroup",
            log_group_name="/aws/lambda/hello-api",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        # --- Lambda Function ---
        fn = _lambda.Function(
            self,
            "HelloApiLambda",
            function_name="hello-api",
            description="Hello API Lambda with OTel instrumentation via ADOT",
            runtime=_lambda.Runtime.PYTHON_3_12,
            architecture=_lambda.Architecture.ARM_64,
            memory_size=256,
            handler="hello_api.aws_lambda_handler.handler",
            timeout=cdk.Duration.seconds(30),
            code=_lambda.Code.from_asset(
                path=(THIS_DIR / "src").as_posix(),
                exclude=_ASSETS_TO_EXCLUDE,
            ),
            layers=[layer, adot_layer],
            log_group=log_group,
            tracing=_lambda.Tracing.PASS_THROUGH,
            environment={
                # App settings
                "APP_NAME": SERVICE_NAME,
                "OTEL_ENABLED": "true",
                "OTEL_SERVICE_NAME": SERVICE_NAME,
                # The OTel SDK sends to the ADOT collector on localhost
                "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318",
                # ADOT collector config (bundled in src/ via the Code asset)
                "OPENTELEMETRY_COLLECTOR_CONFIG_URI": "/var/task/collector.yaml",
                "OTEL_RESOURCE_ATTRIBUTES": f"service.name={SERVICE_NAME}",
            },
        )

        log_group.grant_write(fn)

        # --- API Gateway ---
        api_gw_log_group = logs.LogGroup(
            self,
            "HelloApiGwAccessLogs",
            log_group_name="/aws/apigateway/access-logs/hello-api/prod",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        api = apigw.LambdaRestApi(
            self,
            "HelloApiGateway",
            rest_api_name="Hello API",
            description="API Gateway for Hello API with OTel",
            handler=fn,
            proxy=False,
            deploy=True,
            binary_media_types=["*/*"],
            deploy_options=apigw.StageOptions(
                stage_name="prod",
                tracing_enabled=True,
                metrics_enabled=True,
                logging_level=apigw.MethodLoggingLevel.INFO,
                access_log_destination=apigw.LogGroupLogDestination(log_group=api_gw_log_group),
                access_log_format=_custom_access_log_format(),
            ),
            cloud_watch_role=True,
            cloud_watch_role_removal_policy=cdk.RemovalPolicy.DESTROY,
            endpoint_types=[apigw.EndpointType.REGIONAL],
        )
        api.root.add_method("GET")
        api.root.add_resource("{proxy+}").add_method("ANY")

        # --- Outputs ---
        cdk.CfnOutput(
            self,
            "ApiUrl",
            value=api.url,
            description="Hello API invoke URL",
        )
        cdk.CfnOutput(
            self,
            "LambdaConsoleUrl",
            value=(
                f"https://{self.region}.console.aws.amazon.com/lambda/home"
                f"?region={self.region}#/functions/{fn.function_name}"
            ),
        )
        cdk.CfnOutput(
            self,
            "ApiGatewayConsoleUrl",
            value=(
                f"https://{self.region}.console.aws.amazon.com/apigateway/home"
                f"?region={self.region}#/apis/{api.rest_api_id}/stages/prod"
            ),
        )


def _custom_access_log_format() -> apigw.AccessLogFormat:
    return apigw.AccessLogFormat.custom(
        json.dumps(
            {
                "requestTime": apigw.AccessLogField.context_request_time(),
                "requestId": apigw.AccessLogField.context_request_id(),
                "extendedRequestId": apigw.AccessLogField.context_extended_request_id(),
                "httpMethod": apigw.AccessLogField.context_http_method(),
                "path": apigw.AccessLogField.context_path(),
                "resourcePath": apigw.AccessLogField.context_resource_path(),
                "status": apigw.AccessLogField.context_status(),
                "responseLatency": apigw.AccessLogField.context_response_latency(),
                "xrayTraceId": apigw.AccessLogField.context_xray_trace_id(),
                "integrationRequestId": "$context.integration.requestId",
                "functionResponseStatus": apigw.AccessLogField.context_integration_status(),
                "integrationLatency": apigw.AccessLogField.context_integration_latency(),
                "ip": apigw.AccessLogField.context_identity_source_ip(),
                "userAgent": apigw.AccessLogField.context_identity_user_agent(),
            }
        ),
    )


# --- App ---
app = cdk.App()
cdk.Tags.of(app).add("x-project", "hello-api")
cdk.Tags.of(app).add("x-owner", "auto-monitoring-hackathon")
HelloApiStack(app, "HelloApiStack", env=ENV)
app.synth()
