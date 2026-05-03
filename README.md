# Vultr Kubernetes Platform

This repository contains the infrastructure and platform configuration for a small Kubernetes platform hosted on Vultr.

The platform is designed to be simple, reproducible, cost-conscious and easy to understand after periods of inactivity.

## Goals

- Deploy a small managed Kubernetes cluster on Vultr Kubernetes Engine (VKE).
- Keep monthly costs low.
- Use Infrastructure as Code for Vultr resources.
- Use GitOps for Kubernetes platform components and applications.
- Avoid unnecessary managed services unless they clearly reduce maintenance.
- Keep the repository structure readable and predictable.

## Target Architecture

Vultr DNS
  ↓
VKE worker node public IP
  ↓
Traefik ingress controller
  ↓
Kubernetes services and applications

## Main Components

- Vultr Kubernetes Engine (VKE)
- Pulumi
- GitHub Actions
- Traefik
- cert-manager
- Argo CD
- Vultr DNS

## Deployment Model

GitHub Repository
├── infra/      → Pulumi
├── platform/   → Kubernetes platform components
└── apps/       → Applications

GitHub Actions
  → Runs Pulumi
  → Creates/updates Vultr infrastructure

Argo CD
  → Syncs platform/ and apps/ into Kubernetes

### Flow

1. Infrastructure change
   → Commit to infra/
   → Pulumi preview/up
   → Vultr updated

2. Platform change
   → Commit to platform/
   → Argo CD syncs

3. Application change
   → Commit to apps/
   → Argo CD deploys

## Initial Cluster

- 1 worker node
- 2 vCPU
- 4 GB RAM

## Naming Convention

```text
<service>-<environment>-<sequence>
```

Examples:

- vke-prd-01

## Requirements

Before using this repository, ensure the following tools are installed.

### Required Tools

- Python 3.10 or newer
- uv (Python package and virtual environment manager)
- Pulumi CLI
- Git
- (Optional) vultr-cli for querying Kubernetes versions

### Installation

#### Install uv

See: <https://docs.astral.sh/uv/>

Example:

```bash
curl -Ls https://astral.sh/uv/install.sh | sh
```

#### Install Pulumi CLI

```bash
curl -fsSL https://get.pulumi.com | sh
```

Pulumi installs its binaries in:

```bash
~/.pulumi/bin
```

There are two ways to make the Pulumi CLI available.

##### Option 1: Add Pulumi to PATH

```bash
export PATH="$HOME/.pulumi/bin:$PATH"
```

To make this permanent, add the line to the shell profile, for example:

```bash
~/.bashrc
```

##### Option 2: Symlink Pulumi into ~/.local/bin

If `~/.local/bin` is already in the `PATH`, one can symlink the required Pulumi commands there instead.

For this Python-based project, symlink these binaries:

```bash
ln -s ~/.pulumi/bin/pulumi ~/.local/bin/pulumi
ln -s ~/.pulumi/bin/pulumi-language-python ~/.local/bin/pulumi-language-python
ln -s ~/.pulumi/bin/pulumi-language-python-exec ~/.local/bin/pulumi-language-python-exec
```

Explanation:

- `pulumi` is the main CLI.
- `pulumi-language-python` and `pulumi-language-python-exec` are used for Python Pulumi programs.
- Other Pulumi language binaries such as `pulumi-language-nodejs`, `pulumi-language-go` and `pulumi-language-dotnet` are not needed for this repository.

### Tooling notes

- The Pulumi CLI is required; it is not installed via uv.
- uv manages Python dependencies inside the `infra/` directory.
- Ensure the shell has access to the Pulumi binary before running commands.

### Get available Kubernetes versions (Vultr)

You can query available VKE versions without installing any tools using Docker and a Vultr API key:

```bash
export VULTR_API_KEY=<VULTR_API_KEY>
mkdir -p ~/.config/vultr-cli && touch ~/.config/vultr-cli/vultr-cli.yaml
docker run --rm -e VULTR_API_KEY -v "$HOME/.config/vultr-cli/vultr-cli.yaml:/root/.vultr-cli.yaml:ro" vultr/vultr-cli:latest kubernetes versions
```

Select the latest version (recommended) and update:

```bash
infra/Pulumi.prd.yaml
```

with:

```yaml
config:
  vultr-kubernetes-platform:kubernetes_version: v1.xx.x+1
```

## Initial Setup

Before running any Pulumi commands, one must provide a Vultr API key to the Pulumi configuration.

### Initialize Stack

If this is the first time using the project, create the stack:

```bash
cd infra
pulumi stack init prd
```

If the stack already exists, select it:

```bash
pulumi stack select prd
```

### Set Vultr API Key

There are two ways to provide the Vultr API key.

#### Option 1: Pulumi configuration (encrypted)

```bash
pulumi config set vultr:apiKey --secret
```

You will be prompted to enter your Vultr API key.

Verification:

```bash
pulumi config
```

Expected output:

```text
vultr:apiKey: [secret]
```

Notes:

- The API key is stored as an encrypted secret in `Pulumi.prd.yaml`
- This file can be committed safely, as Pulumi encrypts the value

#### Option 2: Environment variable (recommended)

```bash
export VULTR_API_KEY=<VULTR_API_KEY>
```

Verification:

```bash
echo $VULTR_API_KEY
```

Notes:

- The API key is not stored in the repository at all
- This avoids committing any secrets, even in encrypted form
- This approach is preferred for personal repositories and GitHub usage
- For CI/CD (e.g. GitHub Actions), store `VULTR_API_KEY` as a repository secret

### Deploy Infrastructure

After configuring the Vultr API key, one can deploy the infrastructure.

```bash
cd infra
pulumi up
```

Confirm the plan when prompted.

The deployment will create the Vultr Kubernetes Engine (VKE) cluster. This may take a few minutes.

### Retrieve kubeconfig

After deployment, retrieve the kubeconfig from Pulumi:

```bash
pulumi stack output kubeconfig --show-secrets | base64 -d > kubeconfig.yaml
chmod 600 kubeconfig.yaml
```

### Configure kubectl

Use the generated kubeconfig:

```bash
export KUBECONFIG="$PWD/kubeconfig.yaml"
```

Verify access:

```bash
kubectl get nodes
```

Expected result:

- One node in `Ready` state (may briefly show `NotReady` during initialization)

### Kubernetes configuration notes

- The kubeconfig contains credentials; treat it as sensitive data
- Do not commit `kubeconfig.yaml` to version control (it is added to `.gitignore`)

### Bootstrap Argo CD

Argo CD requires a one-time bootstrap step using `kubectl`. 
After this step, all platform components are managed via Git (GitOps).

Run the bootstrap script:

```bash
./scripts/shell/bootstrap-argocd.sh
```

This script will:

- verify prerequisites (kubectl, environment variables)
- ensure the `argocd` namespace exists
- install Argo CD (if not already installed)
- wait until the Argo CD server is ready

### Access Argo CD

Port-forward the Argo CD server:

```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

Open in browser:

<https://localhost:8080>

### Login

Username:

```text
admin
```

Get the initial password:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d; echo
```

### Change admin password

After logging in:

- Click user icon (top right)
- Select "Update Password"

Then delete the initial secret:

```bash
kubectl -n argocd delete secret argocd-initial-admin-secret
```
## Activate GitOps (repository and root application)

At this point, Argo CD is installed but not yet managing any resources from Git.

Argo CD reads manifests from a remote Git repository. Local changes are not visible to Argo CD.

### Create GitHub repository

Argo CD requires a remote Git repository (e.g. GitHub). Local repositories are not sufficient.

If the repository does not yet exist on GitHub, create it and add it as a remote.

There are two ways to create the repository.

#### Option 1: GitHub web interface

1. Go to https://github.com
2. Create a new repository named:

```text
vultr-kubernetes-platform
```

3. Do not initialize the repository with a README or other files

Then add the remote and push:

```bash
git remote add origin git@github.com:<username>/vultr-kubernetes-platform.git
git add .
git commit -m "Initial Vultr Kubernetes platform release"
git branch -M main
git push -u origin main
```

#### Option 2: GitHub CLI (recommended)

If the GitHub CLI (gh) is installed, the repository can be created and pushed in a single step after commit.

First commit:

```bash
git add .
git commit -m "Initial Vultr Kubernetes platform release"
git branch -M main
```

Then authenticate:

```bash
gh auth login
```

And finally create and push the repository (private):

```bash
gh repo create vultr-kubernetes-platform --private --source=. --remote=origin --push
```

or (public):

```bash
gh repo create vultr-kubernetes-platform --public --source=. --remote=origin --push
```

### Configure root application

Ensure the following file exists:

```bash
platform/bootstrap/root-application.yaml
```

This file defines the root Argo CD application that points to the `platform/` directory in this repository.

### Apply root application

Once the repository is available on GitHub, run:

```bash
./scripts/shell/bootstrap-argocd.sh --bootstrap-root-app
```

This will:

- apply the root Argo CD application
- enable GitOps for the platform
- allow Argo CD to start syncing resources from the repository

### Argo CD and GitOps notes

- The Argo CD bootstrap steps are required only once
- However, the `bootstrap-argocd.sh` script is idempotent and can safely be run multiple times
- Argo CD always reads from the remote repository (GitHub), not the local working tree
- Changes must be committed and pushed before they are applied
- After GitOps activation, all platform components (such as Traefik) are managed declaratively via Git
- Do not manually install components like Traefik; use Argo CD Applications instead
