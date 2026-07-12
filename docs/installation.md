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

## Configure local secrets

```bash
cp secrets.local.env.sample secrets.local.env
```

Set at least:

```bash
VULTR_API_KEY="..."
POSTGRESQL_SUPERUSER_PASSWORD="..."
POSTGRESQL_APP_PASSWORD="..."
```

Also define application-specific secrets using the naming pattern documented in the sample file.

The file is intentionally ignored by Git.

## Initialize the Pulumi stack

```bash
pulumi stack init prd
```

For an existing stack:

```bash
pulumi stack select prd
```

## Deploy infrastructure

```bash
pulumi preview
pulumi up
```

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

From the repository root:

```bash
./scripts/shell/bootstrap-argocd.sh --bootstrap-root-app
```

The script:

- validates prerequisites
- selects the infrastructure configuration
- verifies Kubernetes access
- checks repository URL consistency
- installs Argo CD when required
- applies the root Application when requested
