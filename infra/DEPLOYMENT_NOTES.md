# Deployment Notes: SkyPilot on EKS

## Kubernetes Volumes Explained

This was the main source of confusion during deployment, so let's start here.

### The 3 layers: PVC, PV, and the actual disk

Think of it like renting storage:

```
Your app (Pod)
    ↓ "I need 10Gi of storage please"
PersistentVolumeClaim (PVC)          ← a REQUEST for storage
    ↓ matched to
PersistentVolume (PV)                ← a HANDLE to real storage
    ↓ backed by
EBS Volume (actual disk on AWS)      ← the real, physical disk
```

**PersistentVolumeClaim (PVC):** A request from a pod saying "I need X amount of storage with Y properties." It's like a purchase order. The PVC doesn't contain data -- it's a ticket that says "give me a disk."

**PersistentVolume (PV):** The Kubernetes object that represents an actual provisioned disk. When a PVC is "Bound", it means Kubernetes found (or created) a PV that satisfies the request.

**EBS Volume:** The real AWS disk. This is where bytes live. It costs money. It exists in a specific availability zone.

### Why does a Pod depend on a PVC?

The SkyPilot API server stores its state (database, logs) on disk. If the pod restarts or moves to a different node, it needs to find the same data. Without persistent storage, restarting the pod would wipe everything.

The relationship:
```yaml
# The pod's spec says:
volumes:
  - name: state
    persistentVolumeClaim:
      claimName: skypilot-state    # "attach the disk from this PVC"
```

The pod literally cannot start until its PVC is bound to a real volume. Kubernetes keeps the pod in `Pending` state until the disk is ready.

### What is the EBS CSI driver and why do we need it?

**CSI** = Container Storage Interface. It's a plugin system that teaches Kubernetes how to create and attach disks on a specific cloud provider.

EKS ships with a storage class called `gp2` that says "I want EBS General Purpose SSD volumes." But the storage class is just a *description* -- it doesn't know how to actually call the AWS API to create an EBS volume. That's the CSI driver's job.

```
StorageClass "gp2"
    says: "use provisioner ebs.csi.aws.com"
    says: "volume type = gp2"

EBS CSI Driver (the addon)
    listens for PVCs that reference "ebs.csi.aws.com"
    calls AWS EC2 API → CreateVolume
    attaches the volume to the right EC2 instance
    mounts it into the pod's filesystem
```

Without the EBS CSI driver installed, the `gp2` storage class exists but nothing can actually fulfill requests. PVCs stay `Pending` forever.

### Why did we have to delete the PVC?

When we first deployed, the PVC was created *without* a `storageClassName` (because our Helm values didn't set one). This PVC got stuck in a bad state -- it was trying to find a volume but had no storage class telling it how.

After fixing the values to include `storageClassName: gp2`, Helm upgraded the deployment but **PVCs are immutable once created** -- Kubernetes won't update an existing PVC's storage class. We had to delete it so the Helm chart would create a fresh PVC with the correct storage class.

Deleting a PVC that was never bound (never had a real volume) is safe -- there's no data to lose. If it *had* been bound, deleting the PVC would (by default with `reclaimPolicy: Delete`) also delete the underlying EBS volume and all its data.


## What Went Wrong: The Debugging Timeline

### Problem 1: `kubectl_layer` missing

**What happened:** `cdk synth` failed with `TypeError: Cluster.__init__() missing 1 required keyword-only argument: 'kubectl_layer'`

**Why:** CDK uses a Lambda function to run `kubectl` commands against your cluster (e.g., to set up the aws-auth ConfigMap that controls who can access the cluster). This Lambda needs a "layer" containing the kubectl binary. CDK used to bundle one, but now requires you to provide it explicitly to ensure version compatibility.

**Fix:** Added `aws-cdk.lambda-layer-kubectl-v30` to the PEP 723 dependencies and passed `kubectl_layer=KubectlV30Layer(self, "KubectlLayer")` to the cluster.

### Problem 2: CDK deploy blocked on approval

**What happened:** CDK printed the IAM changes and exited with `"--require-approval" is enabled and stack includes security-sensitive updates, but terminal (TTY) is not attached`

**Why:** By default, CDK asks for interactive confirmation when creating IAM roles/policies (security changes). Since Claude Code runs commands without a TTY, there's no way to type "y".

**Fix:** Added `--require-approval never` to the deploy command. This is acceptable because we're deploying a fresh stack and can review the IAM changes in the `cdk synth` output beforehand.

### Problem 3: SkyPilot resource check failed

**What happened:** `Error: UPGRADE FAILED: Deploying a SkyPilot API server requires at least 4 CPU cores and 8 GiB memory.`

**Why:** The SkyPilot Helm chart has a built-in validation that rejects resource requests below 4 CPU / 8Gi. Our `t3.medium` nodes only have 2 vCPU / 4 GB each, so we set smaller requests to fit.

**Fix:** Set `apiService.skipResourceCheck: true` in the Helm values to bypass the check. This is a conscious trade-off for the hackathon -- see Trade-offs section below.

### Problem 4: PVC stuck in Pending (no storage class)

**What happened:** `kubectl get pvc` showed `skypilot-state` as `Pending` with no storage class.

**Why:** Our initial `skypilot-values.yaml` didn't set `storageClassName`. The PVC was created without one, so Kubernetes didn't know which provisioner to use.

**Fix:** Added `storageClassName: gp2` to the values and deleted the stuck PVC so Helm would recreate it correctly.

### Problem 5: PVC stuck in Pending (EBS CSI driver not installed)

**What happened:** Even with `storageClassName: gp2`, the PVC events showed: `Waiting for a volume to be created either by the external provisioner 'ebs.csi.aws.com'`

**Why:** EKS does not install the EBS CSI driver by default. The `gp2` StorageClass references `ebs.csi.aws.com` as its provisioner, but that provisioner wasn't running.

**Fix:** Installed the `aws-ebs-csi-driver` EKS addon:
```bash
aws eks create-addon --cluster-name skypilot-eks --addon-name aws-ebs-csi-driver
```

### Problem 6: EBS CSI driver can't create volumes (IAM permissions)

**What happened:** PVC events showed: `UnauthorizedOperation: You are not authorized to perform: ec2:CreateVolume`

**Why:** The EBS CSI driver runs as pods in the cluster. Those pods need AWS IAM permissions to call `ec2:CreateVolume`, `ec2:AttachVolume`, etc. By default, the CSI driver pods inherit the node's IAM role, which doesn't include EBS permissions.

**Fix:** This required 3 steps:
1. **Register the OIDC provider** -- This is what enables IRSA (IAM Roles for Service Accounts). It tells AWS "trust tokens signed by this EKS cluster's identity provider." Without this, Kubernetes service accounts can't assume IAM roles.
2. **Create an IAM role** with the `AmazonEBSCSIDriverPolicy` and a trust policy that says "the `ebs-csi-controller-sa` service account in the `kube-system` namespace can assume this role."
3. **Update the addon** to use this role: `aws eks update-addon --service-account-role-arn <role-arn>`

After this, we restarted the CSI controller pods so they'd pick up the new credentials, and the PVC immediately bound.


## What We Mutated In-Place (and How to Automate It)

These things were done manually via CLI and need to be added to the CDK stack or run script:

| Manual step | How to automate |
|---|---|
| Install `aws-ebs-csi-driver` addon | Add to CDK stack as `eks.CfnAddon` |
| Register OIDC provider | CDK does this automatically when you use `cluster.add_service_account()` |
| Create IRSA role for EBS CSI | Add IAM role + policy in CDK stack |
| Attach role to addon | Set `service_account_role_arn` on the `CfnAddon` |

The CDK stack needs these additions to work from scratch:

```python
# 1. Create a service account IAM role for the EBS CSI driver
ebs_csi_role = iam.Role(
    self, "EbsCsiRole",
    assumed_by=iam.FederatedPrincipal(
        cluster.open_id_connect_provider.open_id_connect_provider_arn,
        conditions={
            "StringEquals": {
                f"{cluster.cluster_open_id_connect_issuer}:sub":
                    "system:serviceaccount:kube-system:ebs-csi-controller-sa",
                f"{cluster.cluster_open_id_connect_issuer}:aud":
                    "sts.amazonaws.com",
            }
        },
        assume_role_action="sts:AssumeRoleWithWebIdentity",
    ),
)
ebs_csi_role.add_managed_policy(
    iam.ManagedPolicy.from_aws_managed_policy_name(
        "service-role/AmazonEBSCSIDriverPolicy"
    )
)

# 2. Install the EBS CSI driver addon, pointing it at the role
eks.CfnAddon(
    self, "EbsCsiAddon",
    addon_name="aws-ebs-csi-driver",
    cluster_name=cluster.cluster_name,
    service_account_role_arn=ebs_csi_role.role_arn,
    resolve_conflicts="OVERWRITE",
)
```


## Trade-offs

### Small nodes (t3.medium) with reduced API server resources

**What we chose:** t3.medium (2 vCPU, 4 GB RAM) with SkyPilot requesting 1 CPU / 2 GB.

**The default:** SkyPilot recommends 4 CPU / 8 GB minimum for the API server.

**Risk:** Under heavy load (many concurrent jobs, large cluster state), the API server may become slow or OOM-killed. For 4 intermittent users at a hackathon, this is fine. For production, use at least `m5.large` (2 vCPU, 8 GB) or `m5.xlarge` (4 vCPU, 16 GB).

### `--require-approval never`

**What we chose:** Skip interactive IAM review during `cdk deploy`.

**Risk:** CDK won't warn you if a code change accidentally grants overly broad permissions. Mitigated by running `cdk synth` and reviewing the diff before deploying. For a hackathon this is fine; for production, use `broadening` and deploy from a CI pipeline that can handle the prompt.

### `email-domain: "*"` (OAuth)

**What we chose:** Allow any Google account to authenticate.

**Risk:** Anyone who discovers your load balancer URL can log in with their Google account. The URL is not publicly listed, so the practical risk is low. For production, restrict to your domain (`email-domain: mycompany.com`) or use the Google OAuth consent screen's "test users" list (which is what we did -- only `eric.riddoch@gmail.com` and `avr@gmail.com` are listed as test users, so only they can complete the OAuth flow while the app is in "Testing" mode).

### gp2 storage class (not gp3)

**What we chose:** `gp2` (the default EKS storage class).

**gp3** is newer, cheaper, and faster (3,000 IOPS baseline vs gp2's burstable model). For a 10Gi volume the cost difference is negligible, but if you're creating a fresh cluster you could define a gp3 StorageClass and use that instead.

### Single-AZ volume binding

**What we chose:** `WaitForFirstConsumer` volume binding mode (the gp2 default).

**What this means:** The EBS volume is created in the same availability zone as the node the pod lands on. If that node dies and the replacement lands in a different AZ, the volume can't be attached. With 2 nodes across 2 AZs and only 1 replica of the API server, there's a chance a reschedule fails. For a hackathon, this is fine. For production, consider using EFS (multi-AZ) or running multiple replicas.
