# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "diagrams>=0.24.1",
# ]
# ///
"""
Kubernetes topology diagram for the Auto-Monitoring observability stack.

Shows pods, volume mounts, services, and mappings to AWS services (S3, EBS, IAM).

Usage:
    uv run infra/kubernetes_topology.py
"""

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import EKS
from diagrams.aws.network import PrivateSubnet
from diagrams.aws.security import IAMRole
from diagrams.aws.storage import EBS, S3
from diagrams.k8s.compute import DaemonSet, Deployment
from diagrams.k8s.network import Service
from diagrams.k8s.storage import PVC

with Diagram(
    "Auto-Monitoring — Kubernetes Topology",
    filename="infra/kubernetes-topology",
    show=False,
    direction="TB",
    outformat="png",
    graph_attr={"fontsize": "14", "pad": "0.5"},
):
    # ── External traffic ──────────────────────────────────────────
    apps = EKS("Application\nPods\n(OTLP)")

    with Cluster("AWS Account · us-west-2"):

        # ── S3 long-term storage ──────────────────────────────────
        s3_bucket = S3("S3\nObservability\nBucket")
        ebs = EBS("EBS gp3\nVolumes")

        # ── IRSA IAM Roles ────────────────────────────────────────
        with Cluster("IRSA"):
            iam_mimir = IAMRole("mimir-sa\nRole")
            iam_loki = IAMRole("loki-sa\nRole")
            iam_tempo = IAMRole("tempo-sa\nRole")
            iam_pyro = IAMRole("pyroscope-sa\nRole")

        with Cluster("EKS: auto-monitoring (K8s 1.31)\nPrivate Subnets · m5.large × 2-4"):

            with Cluster("Namespace: monitoring"):

                # ── Collection layer ──────────────────────────────
                with Cluster("Collection"):
                    alloy_svc = Service("alloy\n:4317 :4318\n:12347")
                    alloy_dep = Deployment("Alloy\nv1.13.0")

                    ne_svc = Service("node-exporter\n:9100")
                    ne_ds = DaemonSet("Node\nExporter\nv1.8.2")

                # ── Storage backends ──────────────────────────────
                with Cluster("Metrics"):
                    mimir_svc = Service("mimir\n:8080")
                    mimir_dep = Deployment("Mimir\nv2.14.0")
                    mimir_pvc = PVC("mimir-data\n10Gi")

                with Cluster("Logs"):
                    loki_svc = Service("loki\n:3100")
                    loki_dep = Deployment("Loki\nv3.3.2")
                    loki_pvc = PVC("loki-data\n10Gi")

                with Cluster("Traces"):
                    tempo_svc = Service("tempo\n:3200 :4317")
                    tempo_dep = Deployment("Tempo\nv2.6.1")
                    tempo_pvc = PVC("tempo-data\n10Gi")

                with Cluster("Profiling"):
                    pyro_svc = Service("pyroscope\n:4040")
                    pyro_dep = Deployment("Pyroscope\nv1.10.0")
                    pyro_pvc = PVC("pyroscope-data\n10Gi")

                # ── Visualization ─────────────────────────────────
                with Cluster("Visualization"):
                    graf_svc = Service("grafana\n:80")
                    graf_dep = Deployment("Grafana\nv11.4.0")
                    graf_pvc = PVC("grafana-data\n5Gi")

    # ── Service → Deployment wiring ───────────────────────────────
    alloy_svc >> alloy_dep
    ne_svc >> ne_ds
    mimir_svc >> mimir_dep
    loki_svc >> loki_dep
    tempo_svc >> tempo_dep
    pyro_svc >> pyro_dep
    graf_svc >> graf_dep

    # ── Volume mounts (Deployment → PVC) ──────────────────────────
    mimir_dep >> Edge(label="mount", style="dashed") >> mimir_pvc
    loki_dep >> Edge(label="mount", style="dashed") >> loki_pvc
    tempo_dep >> Edge(label="mount", style="dashed") >> tempo_pvc
    pyro_dep >> Edge(label="mount", style="dashed") >> pyro_pvc
    graf_dep >> Edge(label="mount", style="dashed") >> graf_pvc

    # ── PVCs → EBS ────────────────────────────────────────────────
    [mimir_pvc, loki_pvc, tempo_pvc, pyro_pvc, graf_pvc] >> Edge(
        label="EBS CSI", style="dotted", color="gray"
    ) >> ebs

    # ── S3 long-term storage ──────────────────────────────────────
    mimir_dep >> Edge(label="blocks/", color="blue") >> s3_bucket
    loki_dep >> Edge(label="chunks/", color="blue") >> s3_bucket
    tempo_dep >> Edge(label="traces/", color="blue") >> s3_bucket
    pyro_dep >> Edge(label="profiles/", color="blue") >> s3_bucket

    # ── IRSA: SA → IAM Role → S3 ─────────────────────────────────
    iam_mimir >> Edge(style="dotted", color="orange") >> s3_bucket
    iam_loki >> Edge(style="dotted", color="orange") >> s3_bucket
    iam_tempo >> Edge(style="dotted", color="orange") >> s3_bucket
    iam_pyro >> Edge(style="dotted", color="orange") >> s3_bucket

    # ── Data flow: Apps → Alloy → Backends ────────────────────────
    apps >> Edge(label="OTLP\ngRPC/HTTP") >> alloy_svc

    alloy_dep >> Edge(label="metrics", color="green") >> mimir_svc
    alloy_dep >> Edge(label="logs", color="purple") >> loki_svc
    alloy_dep >> Edge(label="traces", color="red") >> tempo_svc

    # ── Alloy scrapes infrastructure ──────────────────────────────
    alloy_dep >> Edge(label="scrape", style="dashed", color="gray") >> ne_svc

    # ── Tempo → Mimir (span metrics + service graph) ─────────────
    tempo_dep >> Edge(label="span\nmetrics", color="green", style="dashed") >> mimir_svc

    # ── Grafana queries all four backends ─────────────────────────
    graf_dep >> Edge(label="PromQL", color="green") >> mimir_svc
    graf_dep >> Edge(label="LogQL", color="purple") >> loki_svc
    graf_dep >> Edge(label="TraceQL", color="red") >> tempo_svc
    graf_dep >> Edge(label="profiles", color="brown") >> pyro_svc
