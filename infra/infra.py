# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "aws-cdk-lib>=2.180.0",
#     "constructs>=10.0.0",
#     "aws-cdk.lambda-layer-kubectl-v31",
# ]
# ///
"""
Auto-Monitoring Hackathon - EKS Infrastructure (two-stack layout)

Deploy (both stacks):
    npx cdk deploy --all --app "uv run infra/infra.py" --profile subq-sandbox

Deploy VPC only:
    npx cdk deploy AutoMonitoringVpc --app "uv run infra/infra.py" --profile subq-sandbox

Deploy EKS (after VPC):
    npx cdk deploy AutoMonitoringEks --app "uv run infra/infra.py" --profile subq-sandbox

Destroy:
    npx cdk destroy --all --app "uv run infra/infra.py" --profile subq-sandbox

Update kubeconfig after deploy:
    aws eks update-kubeconfig --name auto-monitoring --region us-west-2 --profile subq-sandbox

Generate kubeconfig for external collaborators (no AWS creds needed):
    bash infra/generate-kubeconfig.sh
"""

import aws_cdk as cdk
from aws_cdk import CfnOutput, Stack, Tags
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_eks as eks
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk.lambda_layer_kubectl_v31 import KubectlV31Layer
from constructs import Construct

CLUSTER_NAME = "auto-monitoring"

ENV = cdk.Environment(account="292783887127", region="us-west-2")


# ──────────────────────────────────────────────
# Stack 1: VPC (deploys fast, survives EKS churn)
# ──────────────────────────────────────────────
class VpcStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        self.vpc = ec2.Vpc(
            self,
            "Vpc",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
            ],
        )

        CfnOutput(self, "VpcId", value=self.vpc.vpc_id)
        Tags.of(self).add("project", "auto-monitoring-hackathon")


# ──────────────────────────────────────────────
# Stack 2: EKS + addons (depends on VpcStack)
# ──────────────────────────────────────────────
class EksStack(Stack):
    def __init__(
        self, scope: Construct, id: str, *, vpc: ec2.IVpc, **kwargs
    ) -> None:
        super().__init__(scope, id, **kwargs)

        # --- IAM: masters role for kubectl admin access ---
        masters_role = iam.Role(
            self,
            "MastersRole",
            assumed_by=iam.AccountRootPrincipal(),
        )

        # --- EKS Cluster ---
        cluster = eks.Cluster(
            self,
            "Cluster",
            cluster_name=CLUSTER_NAME,
            version=eks.KubernetesVersion.V1_31,
            kubectl_layer=KubectlV31Layer(self, "KubectlLayer"),
            vpc=vpc,
            vpc_subnets=[
                ec2.SubnetSelection(
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
                )
            ],
            default_capacity=0,
            endpoint_access=eks.EndpointAccess.PUBLIC_AND_PRIVATE,
            masters_role=masters_role,
        )

        # --- Managed Node Group ---
        nodegroup = cluster.add_nodegroup_capacity(
            "DefaultNodes",
            instance_types=[ec2.InstanceType("m5.large")],
            min_size=2,
            max_size=4,
            desired_size=2,
            disk_size=50,
            subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
        )

        # --- External collaborator access (no AWS credentials needed) ---
        # Creates a ServiceAccount with a long-lived token that can be
        # embedded in a kubeconfig and handed to collaborators directly.
        external_sa = cluster.add_manifest(
            "ExternalAdminSA",
            {
                "apiVersion": "v1",
                "kind": "ServiceAccount",
                "metadata": {
                    "name": "external-admin",
                    "namespace": "kube-system",
                },
            },
        )
        external_token = cluster.add_manifest(
            "ExternalAdminToken",
            {
                "apiVersion": "v1",
                "kind": "Secret",
                "type": "kubernetes.io/service-account-token",
                "metadata": {
                    "name": "external-admin-token",
                    "namespace": "kube-system",
                    "annotations": {
                        "kubernetes.io/service-account.name": "external-admin",
                    },
                },
            },
        )
        external_token.node.add_dependency(external_sa)
        external_binding = cluster.add_manifest(
            "ExternalAdminBinding",
            {
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "kind": "ClusterRoleBinding",
                "metadata": {"name": "external-admin-binding"},
                "roleRef": {
                    "apiGroup": "rbac.authorization.k8s.io",
                    "kind": "ClusterRole",
                    "name": "cluster-admin",
                },
                "subjects": [
                    {
                        "kind": "ServiceAccount",
                        "name": "external-admin",
                        "namespace": "kube-system",
                    }
                ],
            },
        )
        external_binding.node.add_dependency(external_sa)

        # --- EBS CSI Driver (needed for PersistentVolumes) ---
        # Grant the node group role the EBS CSI policy directly (avoids
        # SA name collision with the addon's own service account).
        nodegroup.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AmazonEBSCSIDriverPolicy"
            )
        )
        eks.CfnAddon(
            self,
            "EbsCsiAddon",
            addon_name="aws-ebs-csi-driver",
            cluster_name=cluster.cluster_name,
            resolve_conflicts="OVERWRITE",
        )

        # --- S3 Bucket for Observability Long-Term Storage ---
        obs_bucket = s3.Bucket(
            self,
            "ObservabilityBucket",
            removal_policy=cdk.RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
        )

        # --- Monitoring Namespace ---
        monitoring_ns = cluster.add_manifest(
            "MonitoringNamespace",
            {
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {
                    "name": "monitoring",
                    "labels": {
                        "app.kubernetes.io/part-of": "monitoring-stack"
                    },
                },
            },
        )

        # --- IRSA Service Accounts for S3 access ---
        for svc in ["mimir", "loki", "tempo", "pyroscope"]:
            sa = cluster.add_service_account(
                f"{svc.capitalize()}SA",
                name=svc,
                namespace="monitoring",
            )
            sa.node.add_dependency(monitoring_ns)
            obs_bucket.grant_read_write(sa)

        # --- Outputs ---
        CfnOutput(self, "ClusterName", value=cluster.cluster_name)
        CfnOutput(self, "ClusterEndpoint", value=cluster.cluster_endpoint)
        CfnOutput(self, "MastersRoleArn", value=masters_role.role_arn)
        CfnOutput(
            self,
            "KubeconfigCommand",
            value=(
                f"aws eks update-kubeconfig"
                f" --name {cluster.cluster_name}"
                f" --region {self.region}"
                f" --role-arn {masters_role.role_arn}"
                f" --profile subq-sandbox"
            ),
        )
        CfnOutput(self, "ObsBucketName", value=obs_bucket.bucket_name)

        Tags.of(self).add("project", "auto-monitoring-hackathon")


# --- App ---
app = cdk.App()

vpc_stack = VpcStack(app, "AutoMonitoringVpc", env=ENV)

eks_stack = EksStack(app, "AutoMonitoringEks", vpc=vpc_stack.vpc, env=ENV)
eks_stack.add_dependency(vpc_stack)

app.synth()
