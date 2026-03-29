# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "aws-cdk-lib>=2.170.0",
#     "constructs>=10.0.0,<11.0.0",
#     "aws-cdk.lambda-layer-kubectl-v30",
# ]
# ///
#
# Deploy an EKS cluster for SkyPilot on AWS.
#
# Usage:
#   ./run cdk-deploy
#
# Prerequisites:
#   - AWS CLI configured with the "mlops-club" profile
#   - CDK bootstrapped: ./run cdk-bootstrap

import aws_cdk as cdk
from aws_cdk import (
    Stack,
    CfnOutput,
    CfnJson,
    aws_ec2 as ec2,
    aws_eks as eks,
    aws_iam as iam,
    aws_route53 as route53,
    aws_certificatemanager as acm,
)
import os
from aws_cdk.lambda_layer_kubectl_v30 import KubectlV30Layer
from constructs import Construct

DOMAIN = "skypilot.subq-sandbox.com"
PARENT_DOMAIN = "subq-sandbox.com"


class SkyPilotEksStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # VPC with 2 AZs, public + private subnets
        vpc = ec2.Vpc(
            self,
            "SkyPilotVpc",
            max_azs=2,
            nat_gateways=1,
        )

        # IAM role for the EKS cluster admin
        cluster_admin_role = iam.Role(
            self,
            "ClusterAdminRole",
            assumed_by=iam.AccountRootPrincipal(),
        )

        # EKS cluster
        cluster = eks.Cluster(
            self,
            "SkyPilotCluster",
            cluster_name="skypilot-eks",
            version=eks.KubernetesVersion.V1_30,
            kubectl_layer=KubectlV30Layer(self, "KubectlLayer"),
            vpc=vpc,
            default_capacity=0,
            masters_role=cluster_admin_role,
            endpoint_access=eks.EndpointAccess.PUBLIC_AND_PRIVATE,
        )

        # EBS CSI driver — required for Kubernetes to provision EBS volumes (PVCs).
        # Without this, the gp2 StorageClass exists but nothing can actually create disks.
        # CfnJson defers key resolution to deploy-time (OIDC issuer is a CloudFormation token)
        oidc_issuer = cluster.cluster_open_id_connect_issuer
        conditions = CfnJson(
            self,
            "EbsCsiCondition",
            value={
                f"{oidc_issuer}:sub": "system:serviceaccount:kube-system:ebs-csi-controller-sa",
                f"{oidc_issuer}:aud": "sts.amazonaws.com",
            },
        )
        ebs_csi_role = iam.Role(
            self,
            "EbsCsiRole",
            assumed_by=iam.FederatedPrincipal(
                cluster.open_id_connect_provider.open_id_connect_provider_arn,
                conditions={"StringEquals": conditions},
                assume_role_action="sts:AssumeRoleWithWebIdentity",
            ),
        )
        ebs_csi_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AmazonEBSCSIDriverPolicy"
            )
        )
        # Equivalent of: aws eks create-addon --addon-name aws-ebs-csi-driver --service-account-role-arn <role>
        eks.CfnAddon(
            self,
            "EbsCsiAddon",
            addon_name="aws-ebs-csi-driver",
            cluster_name=cluster.cluster_name,
            service_account_role_arn=ebs_csi_role.role_arn,
            resolve_conflicts="OVERWRITE",
        )

        # gp3 StorageClass — cheaper and faster than gp2 (3,000 IOPS baseline vs burstable).
        # EKS only ships gp2 by default, so we create gp3 ourselves.
        cluster.add_manifest("Gp3StorageClass", {
            "apiVersion": "storage.k8s.io/v1",
            "kind": "StorageClass",
            "metadata": {"name": "gp3"},
            "provisioner": "ebs.csi.aws.com",
            "parameters": {"type": "gp3"},
            "reclaimPolicy": "Delete",
            "volumeBindingMode": "WaitForFirstConsumer",
            "allowVolumeExpansion": True,
        })

        # Managed node group — CPU instances for the SkyPilot API server
        cluster.add_nodegroup_capacity(
            "SkyPilotNodes",
            instance_types=[ec2.InstanceType("t3.medium")],
            min_size=1,
            desired_size=2,
            max_size=3,
            disk_size=30,
            capacity_type=eks.CapacityType.ON_DEMAND,
            labels={"role": "skypilot"},
        )

        # ACM certificate for skypilot.subq-sandbox.com with DNS validation via Route 53
        zone = route53.HostedZone.from_lookup(
            self, "SubqZone", domain_name=PARENT_DOMAIN
        )
        cert = acm.Certificate(
            self,
            "SkyPilotCert",
            domain_name=DOMAIN,
            validation=acm.CertificateValidation.from_dns(zone),
        )

        # external-dns IRSA role — allows the external-dns pod to manage Route 53 records
        external_dns_conditions = CfnJson(
            self,
            "ExternalDnsCondition",
            value={
                f"{oidc_issuer}:sub": "system:serviceaccount:external-dns:external-dns",
                f"{oidc_issuer}:aud": "sts.amazonaws.com",
            },
        )
        external_dns_role = iam.Role(
            self,
            "ExternalDnsRole",
            assumed_by=iam.FederatedPrincipal(
                cluster.open_id_connect_provider.open_id_connect_provider_arn,
                conditions={"StringEquals": external_dns_conditions},
                assume_role_action="sts:AssumeRoleWithWebIdentity",
            ),
        )
        external_dns_role.add_to_policy(
            iam.PolicyStatement(
                actions=["route53:ChangeResourceRecordSets"],
                resources=[f"arn:aws:route53:::hostedzone/{zone.hosted_zone_id}"],
            )
        )
        external_dns_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "route53:ListHostedZones",
                    "route53:ListResourceRecordSets",
                    "route53:ListTagsForResource",
                ],
                resources=["*"],
            )
        )

        # Outputs
        CfnOutput(self, "ClusterName", value=cluster.cluster_name)
        CfnOutput(self, "ClusterEndpoint", value=cluster.cluster_endpoint)
        CfnOutput(self, "ClusterArn", value=cluster.cluster_arn)
        CfnOutput(self, "ClusterOidcIssuer", value=cluster.cluster_open_id_connect_issuer)
        CfnOutput(self, "VpcId", value=vpc.vpc_id)
        CfnOutput(self, "CertificateArn", value=cert.certificate_arn)
        CfnOutput(self, "Domain", value=DOMAIN)
        CfnOutput(
            self,
            "ClusterAdminRoleArn",
            value=cluster_admin_role.role_arn,
        )
        CfnOutput(
            self,
            "ExternalDnsRoleArn",
            value=external_dns_role.role_arn,
        )
        CfnOutput(self, "HostedZoneId", value=zone.hosted_zone_id)


app = cdk.App()
SkyPilotEksStack(
    app,
    "SkyPilotEksStack",
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region="us-west-2",
    ),
)
app.synth()
