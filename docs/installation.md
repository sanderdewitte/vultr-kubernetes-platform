# Installation

## Requirements

Install:

- Python 3.10 or newer
- uv
- Pulumi CLI
- Git
- kubectl
- curl

Optional:

- GitHub CLI
- vultr-cli

## Install uv

```bash
curl -Ls https://astral.sh/uv/install.sh | sh
```

## Install Pulumi

```bash
curl -fsSL https://get.pulumi.com | sh
```

Add Pulumi to `PATH`:

```bash
export PATH="$HOME/.pulumi/bin:$PATH"
```

## Create the Pulumi configuration

```bash
cd infra
cp Pulumi.sample.yaml Pulumi.prd.yaml
```

Edit `Pulumi.prd.yaml` and configure:

- repository URL
- region
- cluster name
- Kubernetes version
- worker node plan
- worker node count
- DNS TTL
- domains and applications

Leave bootstrap mode disabled during normal operation.<br>
It is enabled temporarily for the initial platform bootstrap below.

## Configure local secrets

```bash
cp secrets.local.env.sample secrets.local.env
```

Set the Vultr API key:

```bash
VULTR_API_KEY="..."
```

The initial Pulumi bootstrap requires only the Vultr API key.

Before completing the platform deployment, also configure the PostgreSQL secrets:

```bash
POSTGRESQL_SUPERUSER_PASSWORD="..."
POSTGRESQL_APP_PASSWORD="..."


Also define application-specific secrets using the naming pattern documented in the sample file before the final Pulumi deployment.

The file is intentionally ignored by Git.

## Initialize the Pulumi stack

```bash
pulumi stack init prd
```

For an existing stack:

```bash
pulumi stack select prd
```

## Bootstrap infrastructure

The initial deployment needs to run Pulumi in bootstrap mode.<br>
This creates the infrastructure required to start the Kubernetes platform while deferring in-cluster resources until Argo CD has bootstrapped the platform components.

Temporarily enable bootstrap mode in `Pulumi.prd.yaml`:

```yaml
vultr-kubernetes-platform:bootstrap: true
```

As an extra safety measure, bootstrap mode requires explicit confirmation.<br>
For confirmation, set the following environment variable for the initial deployment:

```bash
export VULTR_KUBERNETES_PLATFORM_BOOTSTRAP_CONFIRM=true
```

Preview and deploy the bootstrap infrastructure:

```bash
pulumi preview
pulumi up
```

Unset the confirmation variable immediately afterwards:

```bash
unset VULTR_KUBERNETES_PLATFORM_BOOTSTRAP_CONFIRM
```

Do not disable bootstrap mode in `Pulumi.prd.yaml` yet.<br>
The Kubernetes platform components must first be bootstrapped through Argo CD.

## Retrieve kubeconfig

```bash
pulumi stack output kubeconfig --show-secrets | base64 -d > kubeconfig.yaml
chmod 600 kubeconfig.yaml
```

Install it:

```bash
mkdir -p ~/.kube
cp kubeconfig.yaml ~/.kube/config
chmod 600 ~/.kube/config
```

Verify:

```bash
kubectl get nodes
```

## Bootstrap Argo CD

Return to the repository root and bootstrap Argo CD together with the root Application:

```bash
cd ..
./scripts/shell/bootstrap-argocd.sh --bootstrap-root-app
```

The script:

- validates prerequisites
- selects the infrastructure configuration
- verifies Kubernetes access
- checks repository URL consistency
- installs Argo CD when required
- waits for the Argo CD server deployment
- applies the root Application when requested

The root Application starts the GitOps reconciliation of the platform components.

## Verify platform bootstrap

Allow Argo CD to reconcile the platform components before completing the Pulumi deployment.

Inspect the Argo CD applications:

```bash
kubectl get applications -n argocd
```

The platform applications should become `Synced` and `Healthy`.

The repository also includes the Argo CD Git revision check script,<br>
which can be used to verify application state and deployed Git revisions:

```bash
./scripts/shell/argocd-git-revision-check.sh --all
```

If applications are still progressing, wait for Argo CD to finish reconciling before continuing.

## Complete the platform deployment

Before the normal Pulumi deployment, ensure that the PostgreSQL and required<br>
application-specific secrets have been configured in `secrets.local.env`.

Remove the following temporary setting from `infra/Pulumi.prd.yaml`:

```yaml
vultr-kubernetes-platform:bootstrap: true
```

Bootstrap mode defaults to `false` when the setting is absent.

Return to the infrastructure directory:

```bash
cd infra
```

Preview and deploy the complete platform:

```bash
pulumi preview
pulumi up
```

This creates the in-cluster resources managed by Pulumi, including<br>
Kubernetes Secrets, the PostgreSQL platform database resources and<br>
Argo CD Applications for configured domain applications.

If a platform prerequisite has not finished reconciling yet,<br>
the Pulumi run may fail.

If so, wait for Argo CD to complete the relevant deployment and run:

```bash
 `pulumi up`
```

again.
