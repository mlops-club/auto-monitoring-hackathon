# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "diagrams>=0.24.1",
# ]
# ///
"""
Generate an architecture diagram for the Auto-Monitoring EKS infrastructure.

Usage:
    uv run infra/diagram.py
"""

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import EKS
from diagrams.aws.network import InternetGateway, NATGateway, PrivateSubnet, PublicSubnet
from diagrams.aws.security import IAMRole
from diagrams.aws.storage import EBS
from diagrams.k8s.rbac import ClusterRoleBinding, ServiceAccount
from diagrams.onprem.client import User

with Diagram(
    "Auto-Monitoring EKS",
    filename="infra/eks-architecture",
    show=False,
    direction="TB",
    outformat="png",
):
    collaborators = User("External\nCollaborators\n(kubectl)")
    admin = User("Admin\n(you)")

    with Cluster("AWS Account: 292783887127\nus-west-2"):
        masters_role = IAMRole("Masters Role\n(IAM admin)")

        with Cluster("VPC"):
            igw = InternetGateway("IGW")

            with Cluster("Public Subnets (2 AZs)"):
                pub_a = PublicSubnet("Public\nus-west-2a")
                pub_b = PublicSubnet("Public\nus-west-2b")

            nat = NATGateway("NAT Gateway")

            with Cluster("Private Subnets (2 AZs)"):
                priv_a = PrivateSubnet("Private\nus-west-2a")
                priv_b = PrivateSubnet("Private\nus-west-2b")

            with Cluster("EKS: auto-monitoring (K8s 1.31)"):
                eks_cp = EKS("Control Plane\n(Public + Private\nEndpoint)")

                with Cluster("Managed Node Group\n(m5.large, 2-4 nodes)"):
                    ebs = EBS("EBS CSI Driver")

                with Cluster("kube-system auth"):
                    sa = ServiceAccount("external-admin\nServiceAccount")
                    crb = ClusterRoleBinding("cluster-admin\nBinding")

    # Collaborators: token-based auth (no AWS creds needed)
    collaborators >> Edge(label="bearer token\n(kubeconfig)") >> eks_cp
    sa >> Edge(style="dashed", label="long-lived\ntoken") >> collaborators

    # Admin: IAM-based auth
    admin >> Edge(label="IAM auth") >> masters_role
    masters_role >> Edge(style="dashed", label="system:masters") >> eks_cp

    # RBAC
    crb >> Edge(style="dotted") >> sa

    # Network flow
    igw >> [pub_a, pub_b]
    pub_a >> nat
    nat >> [priv_a, priv_b]
    [priv_a, priv_b] >> eks_cp
