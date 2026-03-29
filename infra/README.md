# infra

EKS cluster + SkyPilot for the hackathon.

## Setup

```bash
aws sso login --profile mlops-club
./run cdk-bootstrap       # one-time
./run cdk-deploy           # deploy EKS cluster + ACM cert + IAM roles
./run get-kubeconfig       # merge cluster into kubeconfig
# fill in .env with Google OAuth credentials (see .env.example)
./run install-skypilot     # install oauth2-proxy + SkyPilot + external-dns
```

## Architecture

```mermaid
graph TB
    subgraph Internet
        Browser["Browser"]
    end

    subgraph AWS
        R53["Route 53 CNAME<br/>skypilot.subq-sandbox.com"]
        ACM["ACM Certificate"]
        NLB["Network Load Balancer<br/>TLS termination"]
    end

    subgraph EKS["EKS Cluster"]
        subgraph ns_skypilot["namespace: skypilot"]
            subgraph helm_skypilot["Helm chart: skypilot"]
                nginx["Pod: ingress-nginx-controller"]
                nginx_svc["Svc: ingress-nginx-controller<br/>LoadBalancer"]
                skypilot_pod["Pod: skypilot-api-server<br/>skypilot-nightly + logrotate"]
                skypilot_svc["Svc: skypilot-api-service<br/>ClusterIP"]
                skypilot_ingress["Ingress: skypilot-ingress<br/>path /"]
                pvc["PVC: skypilot-state<br/>10Gi gp3 EBS"]
                skypilot_cm["ConfigMap: skypilot-config"]
            end

            subgraph helm_oauth2["Helm chart: oauth2-proxy"]
                oauth2_pod["Pod: oauth2-proxy"]
                oauth2_svc["Svc: oauth2-proxy<br/>ClusterIP"]
                oauth2_ingress["Ingress: oauth2-proxy<br/>path /oauth2"]
                oauth2_secret["Secret: oauth2-proxy<br/>client-id, client-secret"]
                oauth2_cm["ConfigMap: oauth2-proxy-accesslist<br/>email allowlist"]
            end
        end

        subgraph ns_externaldns["namespace: external-dns"]
            subgraph helm_extdns["Helm chart: external-dns"]
                extdns_pod["Pod: external-dns"]
                extdns_sa["ServiceAccount: external-dns<br/>IRSA"]
            end
        end
    end

    Browser -->|"HTTPS :443"| R53
    R53 -->|CNAME| NLB
    ACM -.->|TLS cert| NLB
    NLB -->|"HTTP :80"| nginx_svc
    nginx_svc --> nginx

    nginx -->|"auth subrequest /oauth2/auth"| oauth2_svc
    oauth2_svc --> oauth2_pod
    oauth2_pod --- oauth2_secret
    oauth2_pod --- oauth2_cm

    nginx -->|"path /oauth2"| oauth2_ingress
    oauth2_ingress --> oauth2_svc

    nginx -->|"path /"| skypilot_ingress
    skypilot_ingress -->|authenticated| skypilot_svc
    skypilot_svc --> skypilot_pod
    skypilot_pod --- pvc
    skypilot_pod --- skypilot_cm

    extdns_pod -->|watches| nginx_svc
    extdns_pod -->|creates CNAME| R53
    extdns_sa -.->|IRSA| R53
```

## Deployment dependency graph

`./run install-skypilot` deploys three Helm charts in order. The SkyPilot chart bundles its own ingress-nginx subchart.

```mermaid
graph LR
    subgraph CDK["CDK Stack"]
        EKS["EKS Cluster"]
        ACM["ACM Certificate"]
        IRSA_DNS["IAM Role<br/>external-dns IRSA"]
        SC["StorageClass gp3"]
    end

    subgraph Helm1["1. helm install oauth2-proxy"]
        O_Deploy["Deployment oauth2-proxy"]
        O_Svc["Service oauth2-proxy"]
        O_Ingress["Ingress /oauth2"]
        O_Secret["Secret credentials"]
        O_CM["ConfigMap email allowlist"]
    end

    subgraph Helm2["2. helm install skypilot"]
        S_Deploy["Deployment skypilot-api-server"]
        S_Svc["Service skypilot-api-service"]
        S_Ingress["Ingress / with auth"]
        S_PVC["PVC skypilot-state 10Gi"]
        N_Deploy["Deployment ingress-nginx"]
        N_Svc["Service LoadBalancer<br/>ingress-nginx"]
    end

    subgraph Helm3["3. helm install external-dns"]
        E_Deploy["Deployment external-dns"]
        E_SA["ServiceAccount IRSA"]
    end

    subgraph AWS_Runtime["AWS runtime resources"]
        NLB["NLB auto-provisioned"]
        CNAME["Route 53 CNAME"]
    end

    EKS --> Helm1
    EKS --> Helm2
    EKS --> Helm3

    ACM -->|"cert ARN via --set"| N_Svc
    IRSA_DNS -->|"role ARN via --set"| E_SA
    SC -->|storageClassName| S_PVC

    S_Ingress -->|"auth-url points to"| O_Svc
    N_Svc -->|"LB annotation"| NLB
    E_Deploy -->|watches| N_Svc
    E_Deploy -->|upserts| CNAME
```

## OAuth

Google OAuth SSO via a standalone [oauth2-proxy](https://oauth2-proxy.github.io/oauth2-proxy/) deployment (official Helm chart).

- **Google project**: [consent screen](https://console.cloud.google.com/apis/credentials/consent?project=skypilot-hackathon) | [credentials](https://console.cloud.google.com/apis/credentials?project=skypilot-hackathon)
- **Redirect URI**: `https://skypilot.subq-sandbox.com/oauth2/callback`
- **Allowed emails**: edit `authenticatedEmailsFile.restricted_access` in `oauth2-proxy-values.yaml`, then re-run `./run install-skypilot`
- SkyPilot's built-in oauth2-proxy only supports domain filtering. We deploy oauth2-proxy separately (with per-email allowlist support) and use SkyPilot's `auth.externalProxy` to trust the `X-Auth-Request-Email` header.
- NLB terminates TLS but doesn't set `X-Forwarded-Proto`. The `proxySetHeaders` config in `skypilot-values.yaml` forces it to `https` so CSRF cookies work.
- **Browser note**: Brave's bounce-tracking protection blocks the CSRF cookie during the OAuth redirect chain. Use Chrome or lower Brave Shields for this site.

## DNS

`external-dns` automatically manages the `skypilot.subq-sandbox.com` CNAME in Route 53, pointing at the NLB.

## Notes

- [ ] What state does SkyPilot store in the EBS volume PVC vs in a separate Postgres DB?
