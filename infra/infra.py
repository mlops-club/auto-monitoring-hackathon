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
from aws_cdk import aws_certificatemanager as acm
from aws_cdk import aws_route53 as route53
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

        # Tag subnets for ALB controller discovery
        for subnet in self.vpc.public_subnets:
            Tags.of(subnet).add("kubernetes.io/role/elb", "1")
        for subnet in self.vpc.private_subnets:
            Tags.of(subnet).add("kubernetes.io/role/internal-elb", "1")

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
        # Allow sts:TagSession so GitHub Actions can chain into this role
        masters_role.assume_role_policy.add_statements(
            iam.PolicyStatement(
                actions=["sts:TagSession"],
                principals=[iam.AccountRootPrincipal()],
            )
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

        # --- IRSA: Alloy (CloudWatch scraping) ---
        alloy_sa = cluster.add_service_account(
            "AlloySA",
            name="alloy",
            namespace="monitoring",
        )
        alloy_sa.node.add_dependency(monitoring_ns)
        alloy_sa.add_to_principal_policy(
            iam.PolicyStatement(
                actions=[
                    # CloudWatch metrics
                    "cloudwatch:GetMetricData",
                    "cloudwatch:GetMetricStatistics",
                    "cloudwatch:ListMetrics",
                    # Resource discovery (YACE)
                    "tag:GetResources",
                    "iam:ListAccountAliases",
                    # Service-specific describe for YACE auto-discovery
                    "rds:DescribeDBInstances",
                    "rds:DescribeDBClusters",
                    "rds:ListTagsForResource",
                    "apigateway:GET",
                    "lambda:ListFunctions",
                    "lambda:ListTags",
                    # CloudWatch Logs
                    "logs:DescribeLogGroups",
                    "logs:FilterLogEvents",
                    "logs:GetLogEvents",
                ],
                resources=["*"],
            )
        )

        # --- ACM Wildcard Certificate for *.hack.subq-sandbox.com ---
        hosted_zone = route53.HostedZone.from_hosted_zone_attributes(
            self,
            "HackZone",
            hosted_zone_id="Z09554162IC6F7GCC8XO9",
            zone_name="subq-sandbox.com",
        )
        wildcard_cert = acm.Certificate(
            self,
            "WildcardCert",
            domain_name="*.hack.subq-sandbox.com",
            validation=acm.CertificateValidation.from_dns(hosted_zone),
        )

        # --- IRSA: AWS Load Balancer Controller ---
        lb_controller_sa = cluster.add_service_account(
            "LbControllerSA",
            name="aws-load-balancer-controller",
            namespace="kube-system",
        )
        lb_controller_sa.add_to_principal_policy(
            iam.PolicyStatement(
                actions=[
                    "ec2:DescribeAccountAttributes",
                    "ec2:DescribeAddresses",
                    "ec2:DescribeAvailabilityZones",
                    "ec2:DescribeInternetGateways",
                    "ec2:DescribeVpcs",
                    "ec2:DescribeVpcPeeringConnections",
                    "ec2:DescribeSubnets",
                    "ec2:DescribeSecurityGroups",
                    "ec2:DescribeInstances",
                    "ec2:DescribeNetworkInterfaces",
                    "ec2:DescribeTags",
                    "ec2:DescribeCoipPools",
                    "ec2:GetCoipPoolUsage",
                    "ec2:DescribeTargetGroups",
                    "ec2:DescribeTargetHealth",
                    "ec2:DescribeListeners",
                    "ec2:DescribeRules",
                    "ec2:CreateSecurityGroup",
                    "ec2:CreateTags",
                    "ec2:DeleteTags",
                    "ec2:AuthorizeSecurityGroupIngress",
                    "ec2:RevokeSecurityGroupIngress",
                    "ec2:DeleteSecurityGroup",
                    "elasticloadbalancing:*",
                    "cognito-idp:DescribeUserPoolClient",
                    "acm:ListCertificates",
                    "acm:DescribeCertificate",
                    "iam:ListServerCertificates",
                    "iam:GetServerCertificate",
                    "iam:CreateServiceLinkedRole",
                    "waf-regional:GetWebACL",
                    "waf-regional:GetWebACLForResource",
                    "waf-regional:AssociateWebACL",
                    "waf-regional:DisassociateWebACL",
                    "wafv2:GetWebACL",
                    "wafv2:GetWebACLForResource",
                    "wafv2:AssociateWebACL",
                    "wafv2:DisassociateWebACL",
                    "shield:GetSubscriptionState",
                    "shield:DescribeProtection",
                    "shield:CreateProtection",
                    "shield:DeleteProtection",
                ],
                resources=["*"],
            )
        )

        # --- IRSA: external-dns ---
        external_dns_sa = cluster.add_service_account(
            "ExternalDnsSA",
            name="external-dns",
            namespace="kube-system",
        )
        external_dns_sa.add_to_principal_policy(
            iam.PolicyStatement(
                actions=[
                    "route53:ChangeResourceRecordSets",
                ],
                resources=[f"arn:aws:route53:::hostedzone/{hosted_zone.hosted_zone_id}"],
            )
        )
        external_dns_sa.add_to_principal_policy(
            iam.PolicyStatement(
                actions=[
                    "route53:ListHostedZones",
                    "route53:ListResourceRecordSets",
                    "route53:ListTagsForResource",
                ],
                resources=["*"],
            )
        )

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
        CfnOutput(self, "WildcardCertArn", value=wildcard_cert.certificate_arn)
        CfnOutput(self, "LbControllerRoleArn", value=lb_controller_sa.role.role_arn)
        CfnOutput(self, "ExternalDnsRoleArn", value=external_dns_sa.role.role_arn)
        CfnOutput(self, "AlloyRoleArn", value=alloy_sa.role.role_arn)

        Tags.of(self).add("project", "auto-monitoring-hackathon")


# --- App ---
app = cdk.App()

vpc_stack = VpcStack(app, "AutoMonitoringVpc", env=ENV)

eks_stack = EksStack(app, "AutoMonitoringEks", vpc=vpc_stack.vpc, env=ENV)
eks_stack.add_dependency(vpc_stack)

app.synth()
