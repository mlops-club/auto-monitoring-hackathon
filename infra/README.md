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
        Browser[Browser]
    end

    subgraph AWS
        R53[Route 53<br/>skypilot.subq-sandbox.com<br/>CNAME]
        ACM[ACM Certificate<br/>*.subq-sandbox.com]
        NLB[Network Load Balancer<br/>TLS termination on :443]
    end

    subgraph EKS Cluster
        subgraph ns-skypilot [namespace: skypilot]
            subgraph helm-skypilot [Helm: skypilot]
                nginx[Pod: ingress-nginx-controller<br/>ingress-nginx:v1.11.8]
                nginx-svc[Service: ingress-nginx-controller<br/>type: LoadBalancer]
                skypilot-pod[Pod: skypilot-api-server<br/>skypilot-nightly + logrotate]
                skypilot-svc[Service: skypilot-api-service<br/>type: ClusterIP]
                skypilot-ingress[Ingress: skypilot-ingress<br/>path: /]
                pvc[PVC: skypilot-state<br/>10Gi gp3 EBS]
                skypilot-sa[ServiceAccount: skypilot-api-sa]
                skypilot-cm[ConfigMap: skypilot-config<br/>+ skypilot-server-config]
            end

            subgraph helm-oauth2 [Helm: oauth2-proxy]
                oauth2-pod[Pod: oauth2-proxy<br/>oauth2-proxy:v7.15.0]
                oauth2-svc[Service: oauth2-proxy<br/>type: ClusterIP]
                oauth2-ingress[Ingress: oauth2-proxy<br/>path: /oauth2]
                oauth2-secret[Secret: oauth2-proxy<br/>client-id, client-secret, cookie-secret]
                oauth2-cm[ConfigMap: oauth2-proxy<br/>+ oauth2-proxy-accesslist]
            end
        end

        subgraph ns-externaldns [namespace: external-dns]
            subgraph helm-extdns [Helm: external-dns]
                extdns-pod[Pod: external-dns]
                extdns-sa[ServiceAccount: external-dns<br/>IRSA → Route 53]
            end
        end
    end

    Browser -->|HTTPS :443| R53
    R53 -->|CNAME| NLB
    ACM -.->|TLS cert| NLB
    NLB -->|HTTP :80| nginx-svc
    nginx-svc --> nginx

    nginx -->|auth subrequest<br/>/oauth2/auth| oauth2-svc
    oauth2-svc --> oauth2-pod
    oauth2-pod --- oauth2-secret
    oauth2-pod --- oauth2-cm

    nginx -->|path: /oauth2/*| oauth2-ingress
    oauth2-ingress --> oauth2-svc

    nginx -->|path: /| skypilot-ingress
    skypilot-ingress -->|authenticated| skypilot-svc
    skypilot-svc --> skypilot-pod
    skypilot-pod --- pvc
    skypilot-pod --- skypilot-cm

    extdns-pod -->|watches annotations on| nginx-svc
    extdns-pod -->|creates CNAME in| R53
    extdns-sa -.->|IRSA| R53
```

## Deployment dependency graph

`./run install-skypilot` deploys three Helm charts in order. The SkyPilot chart bundles its own ingress-nginx subchart.

```mermaid
graph LR
    subgraph CDK [CDK Stack: SkyPilotEksStack]
        EKS[EKS Cluster]
        ACM[ACM Certificate]
        IRSA_DNS[IAM Role<br/>external-dns IRSA]
        SC[StorageClass: gp3]
    end

    subgraph Helm1 [1. helm install oauth2-proxy]
        O_Deploy[Deployment<br/>oauth2-proxy]
        O_Svc[Service<br/>oauth2-proxy :80]
        O_Ingress[Ingress<br/>/oauth2]
        O_Secret[Secret<br/>client-id, client-secret<br/>cookie-secret]
        O_CM[ConfigMap<br/>email allowlist]
    end

    subgraph Helm2 [2. helm install skypilot]
        S_Deploy[Deployment<br/>skypilot-api-server]
        S_Svc[Service<br/>skypilot-api-service :80]
        S_Ingress[Ingress<br/>/ with auth annotations]
        S_PVC[PVC<br/>skypilot-state 10Gi]
        N_Deploy[Deployment<br/>ingress-nginx-controller]
        N_Svc[Service: LoadBalancer<br/>ingress-nginx :80/:443]
    end

    subgraph Helm3 [3. helm install external-dns]
        E_Deploy[Deployment<br/>external-dns]
        E_SA[ServiceAccount<br/>IRSA-annotated]
    end

    subgraph AWS_Runtime [AWS resources created at runtime]
        NLB[NLB<br/>auto-provisioned]
        CNAME[Route 53 CNAME<br/>auto-managed]
    end

    EKS --> Helm1
    EKS --> Helm2
    EKS --> Helm3

    ACM -->|cert ARN via --set| N_Svc
    IRSA_DNS -->|role ARN via --set| E_SA
    SC -->|storageClassName: gp3| S_PVC

    S_Ingress -->|auth-url annotation<br/>points to| O_Svc
    N_Svc -->|LB annotation triggers| NLB
    E_Deploy -->|reads annotation on| N_Svc
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
