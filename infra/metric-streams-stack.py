# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "aws-cdk-lib>=2.180.0",
#     "constructs>=10.0.0",
# ]
# ///
"""
CloudWatch Metric Streams → OTLP Endpoint (self-contained CDK stack)

Pushes CloudWatch metrics from this AWS account to the Grafana observability
stack via Kinesis Firehose → OTLP HTTP.

This stack is independent of the main EKS infrastructure in infra.py.
Deploy it in any AWS account that has resources you want to monitor.

Deploy:
    npx cdk deploy --app "uv run infra/metric-streams-stack.py" --profile <profile>

Destroy:
    npx cdk destroy --app "uv run infra/metric-streams-stack.py" --profile <profile>

See docs/metric-streams-guide.md for full documentation.
"""

import aws_cdk as cdk
from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_kinesisfirehose as firehose
from aws_cdk import aws_cloudwatch as cloudwatch
from constructs import Construct

# ── Configuration ────────────────────────────────────────────────────
# Point this at your Alloy OTLP ingress. The Firehose delivers to
# this URL with Content-Type: application/x-protobuf.
OTLP_ENDPOINT = "https://otlp.hack.subq-sandbox.com/v1/metrics"

# CloudWatch namespaces to stream. Add or remove as needed.
# Remove the include_filters list entirely to stream ALL namespaces.
METRIC_NAMESPACES = [
    "AWS/RDS",
    "AWS/ApiGateway",
    "AWS/Lambda",
]

ENV = cdk.Environment(region="us-west-2")
# ─────────────────────────────────────────────────────────────────────


class MetricStreamsStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # --- S3 bucket for Firehose backup (failed deliveries) ---
        backup_bucket = s3.Bucket(
            self,
            "FirehoseBackup",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            lifecycle_rules=[
                s3.LifecycleRule(expiration=Duration.days(14)),
            ],
        )

        # --- IAM role for Firehose ---
        firehose_role = iam.Role(
            self,
            "FirehoseRole",
            assumed_by=iam.ServicePrincipal("firehose.amazonaws.com"),
        )
        backup_bucket.grant_read_write(firehose_role)

        # --- Kinesis Firehose delivery stream (HTTP endpoint) ---
        delivery_stream = firehose.CfnDeliveryStream(
            self,
            "OtlpDeliveryStream",
            delivery_stream_name="cloudwatch-metrics-to-otlp",
            delivery_stream_type="DirectPut",
            http_endpoint_destination_configuration=firehose.CfnDeliveryStream.HttpEndpointDestinationConfigurationProperty(
                endpoint_configuration=firehose.CfnDeliveryStream.HttpEndpointConfigurationProperty(
                    url=OTLP_ENDPOINT,
                    name="GrafanaAlloyOTLP",
                ),
                request_configuration=firehose.CfnDeliveryStream.HttpEndpointRequestConfigurationProperty(
                    content_encoding="GZIP",
                    common_attributes=[
                        firehose.CfnDeliveryStream.HttpEndpointCommonAttributeProperty(
                            attribute_name="Content-Type",
                            attribute_value="application/x-protobuf",
                        ),
                    ],
                ),
                buffering_hints=firehose.CfnDeliveryStream.BufferingHintsProperty(
                    interval_in_seconds=60,
                    size_in_m_bs=1,
                ),
                retry_options=firehose.CfnDeliveryStream.RetryOptionsProperty(
                    duration_in_seconds=300,
                ),
                s3_backup_mode="FailedDataOnly",
                s3_configuration=firehose.CfnDeliveryStream.S3DestinationConfigurationProperty(
                    bucket_arn=backup_bucket.bucket_arn,
                    role_arn=firehose_role.role_arn,
                    prefix="failed/",
                    error_output_prefix="errors/",
                    buffering_hints=firehose.CfnDeliveryStream.BufferingHintsProperty(
                        interval_in_seconds=300,
                        size_in_m_bs=5,
                    ),
                    compression_format="GZIP",
                ),
                role_arn=firehose_role.role_arn,
            ),
        )

        # --- IAM role for CloudWatch Metric Stream ---
        stream_role = iam.Role(
            self,
            "MetricStreamRole",
            assumed_by=iam.ServicePrincipal("streams.metrics.cloudwatch.amazonaws.com"),
        )
        stream_role.add_to_policy(
            iam.PolicyStatement(
                actions=["firehose:PutRecord", "firehose:PutRecordBatch"],
                resources=[delivery_stream.attr_arn],
            )
        )

        # --- CloudWatch Metric Stream ---
        include_filters = [
            cloudwatch.CfnMetricStream.MetricStreamFilterProperty(
                namespace=ns,
            )
            for ns in METRIC_NAMESPACES
        ]

        metric_stream = cloudwatch.CfnMetricStream(
            self,
            "MetricStream",
            name="grafana-otlp-stream",
            firehose_arn=delivery_stream.attr_arn,
            role_arn=stream_role.role_arn,
            output_format="opentelemetry0.7",
            include_filters=include_filters if METRIC_NAMESPACES else None,
            statistics_configurations=[
                # Include p50/p99 for latency metrics
                cloudwatch.CfnMetricStream.MetricStreamStatisticsConfigurationProperty(
                    additional_statistics=["p50", "p99"],
                    include_metrics=[
                        cloudwatch.CfnMetricStream.MetricStreamStatisticsMetricProperty(
                            metric_name="Latency",
                            namespace="AWS/ApiGateway",
                        ),
                        cloudwatch.CfnMetricStream.MetricStreamStatisticsMetricProperty(
                            metric_name="Duration",
                            namespace="AWS/Lambda",
                        ),
                        cloudwatch.CfnMetricStream.MetricStreamStatisticsMetricProperty(
                            metric_name="ReadLatency",
                            namespace="AWS/RDS",
                        ),
                        cloudwatch.CfnMetricStream.MetricStreamStatisticsMetricProperty(
                            metric_name="WriteLatency",
                            namespace="AWS/RDS",
                        ),
                    ],
                ),
            ],
        )
        metric_stream.node.add_dependency(delivery_stream)

        # --- Outputs ---
        CfnOutput(self, "DeliveryStreamArn", value=delivery_stream.attr_arn)
        CfnOutput(self, "MetricStreamName", value=metric_stream.name)
        CfnOutput(self, "BackupBucketName", value=backup_bucket.bucket_name)
        CfnOutput(
            self,
            "TargetEndpoint",
            value=OTLP_ENDPOINT,
            description="OTLP endpoint receiving streamed metrics",
        )


# --- App ---
app = cdk.App()
MetricStreamsStack(app, "CloudWatchMetricStreams", env=ENV)
app.synth()
