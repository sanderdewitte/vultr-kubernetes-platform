# Vultr Kubernetes Platform

This repository contains the infrastructure and platform configuration for a small Kubernetes platform hosted on Vultr.

The platform is designed to be simple, reproducible, cost-conscious and easy to understand after periods of inactivity.

## Goals

- Deploy a small managed Kubernetes cluster on Vultr Kubernetes Engine (VKE).
- Keep monthly costs low.
- Use Infrastructure as Code for Vultr resources, shared platform services and application prerequisites.
- Use GitOps for Kubernetes platform components and applications.
- Avoid unnecessary managed services unless they clearly reduce maintenance.
- Prefer secure-by-default configurations and well-established open-source technologies.
- Keep the repository structure readable and predictable.

## Target architecture

This platform is designed as a small, low-cost GitOps-managed Kubernetes environment on Vultr Kubernetes Engine (VKE).

The platform intentionally avoids a managed Vultr Load Balancer. Instead, public traffic enters the cluster through the public IP address of a single VKE worker node.

The intended HTTP/HTTPS traffic flow is:

```text
Vultr DNS
  ↓
Single VKE worker node public IP
  ↓
Node host ports 80/443
  ↓
Traefik ingress controller
    - hostPort 80  → Traefik web entryPoint on port 8000
    - hostPort 443 → Traefik websecure entryPoint on port 8443
  ↓
Kubernetes Ingress / IngressRoute
  ↓
Kubernetes ClusterIP services
  ↓
Application pods
```

Traefik is the only component exposed directly on the worker node. Application workloads should normally use `ClusterIP` Services and rely on Traefik for external HTTP and HTTPS access.

The Traefik container listens on unprivileged ports `8000` and `8443`, while Kubernetes maps the node host ports `80` and `443` to those container ports. This allows Traefik to run without binding directly to privileged ports inside the container.

### DNS model

Vultr DNS is managed through Pulumi.

The DNS model is:

```text
example.com      A      <current VKE worker node public IP>
*.example.com    CNAME  example.com
```

Pulumi derives the current worker node public IP from the VKE node pool and uses it for the apex `A` record. 

If the VKE worker node is replaced and receives a new public IP address, running `pulumi up` updates the DNS `A` record.

### Certificate model

cert-manager is installed as a platform component and uses Let's Encrypt for certificate issuance.

This platform uses ACME DNS-01 validation through the Vultr webhook. The Vultr webhook only adds Vultr integration capability to cert-manager. The actual choice to use DNS-01 and the Vultr webhook is made by the `ClusterIssuer` resources under:

```text
platform/cert-manager/issuers/
```

The Vultr API token is not stored in Git. It is read by Pulumi from `infra/secrets.local.env` and written into Kubernetes as the `vultr-credentials` Secret in the `cert-manager` namespace. The webhook has narrowly scoped RBAC that allows it to read only that Secret.

Two issuers are defined:

```text
letsencrypt-staging     → Let's Encrypt staging environment for testing
letsencrypt-production  → Let's Encrypt production environment for trusted certificates
```

Applications request certificates by referencing one of these issuers from their Ingress annotations and by defining a TLS section with a namespace-local Secret name.

### Scalability and cost trade-off

This setup intentionally uses a single public worker node as the external entry point. This avoids the cost of a managed Vultr Load Balancer and keeps the architecture simple and easy to understand.

This also means the setup is not highly available at the ingress layer. If the worker node that receives public traffic is unavailable, external access to the applications is unavailable.

The Pulumi configuration intentionally validates that the low-cost DNS model is used with one worker node. If the platform is expanded to multiple worker nodes, the ingress architecture should be revisited.

For a more production-grade multi-node setup, the recommended architecture would introduce an external load balancer or another highly available front-end in front of Traefik.

## Main components

Implemented:

- Vultr Kubernetes Engine (VKE)
- Pulumi
- Vultr DNS
- Argo CD
- Traefik
- cert-manager
- cert-manager Vultr webhook
- Let's Encrypt certificate automation using DNS-01
- CloudNativePG operator
- Shared PostgreSQL platform database cluster
- Automatic PostgreSQL role and database provisioning for applications

Planned / next steps:

- Add Authentik as a central identity and access-management platform.
- Integrate selected applications with Authentik where supported.
- Publish selected platform management services through Traefik and central authentication.
- Add metrics-server for basic Kubernetes CPU and memory visibility.
- Add a GitHub Actions workflow for manually triggered Pulumi preview.
- Optionally add a manually approved Pulumi up workflow.

## Deployment model

```text
GitHub Repository
├── infra/      → Pulumi infrastructure code
├── platform/   → Argo CD platform configuration and Application definitions
└── apps/       → Application Kubernetes manifests
```

### Directory responsibilities

`infra/` contains the Pulumi program. It creates and updates Vultr infrastructure, including:

- VKE cluster
- Vultr DNS records
- Shared PostgreSQL platform resources
- Application-specific PostgreSQL roles and databases
- Kubernetes secrets required by platform services and applications

`platform/` contains Kubernetes platform configuration managed by Argo CD. The root Argo CD application watches this directory recursively. Platform components such as Traefik live directly under `platform/`, while normal application `Application` objects live under `platform/apps/`. The CloudNativePG operator itself is deployed through Argo CD from the `platform` directory. The PostgreSQL cluster, roles and databases are managed by Pulumi and therefore do not appear as manifests under `platform/`.

`apps/` contains the actual Kubernetes manifests for application workloads. `platform/apps/` contains Argo CD "Application" objects that tell Argo CD which applications to deploy. The actual application manifests and/or Helm configuration live under `apps/`.

The current pattern is:

```text
    platform/
    ├── argocd/
    │   └── argocd-cm-ingress-health.yaml
    ├── cert-manager/
    │   ├── application.yaml
    │   ├── values.yaml
    │   ├── issuers/
    │   │   ├── clusterissuer-letsencrypt-staging.yaml
    │   │   └── clusterissuer-letsencrypt-production.yaml
    │   └── webhook-vultr/
    │       ├── application.yaml
    │       ├── values.yaml
    │       └── secret-reader-rbac.yaml
    ├── traefik/
    │   ├── application.yaml
    │   └── values.yaml
    ├── cloudnative-pg/
    │   ├── application.yaml
    │   └── values.yaml
    └── apps/
        └── welcome/
            └── application.yaml

    apps/
    └── welcome/
        ├── deployment.yaml
        ├── service.yaml
        └── ingress.yaml
```

### Flow

1. Infrastructure change  
   → Commit to `infra/`  
   → Run `pulumi preview` / `pulumi up`  
   → Vultr infrastructure and DNS are updated  

2. Platform change  
   → Commit to `platform/`  
   → Push to GitHub  
   → Argo CD syncs the platform change  

3. Application change  
   → Commit to `apps/` and, when needed, `platform/apps/`  
   → Push to GitHub  
   → Argo CD deploys or updates the application  

Argo CD reads from the remote GitHub repository, not from the local working tree. Changes must be committed and pushed before Argo CD can apply them.

## Initial cluster

- 1 worker node
- 2 vCPU
- 4 GB RAM

## Worker node maintenance

VKE worker nodes are managed as part of the Vultr Kubernetes Engine service. They should not be treated like manually maintained servers.

Do not SSH into the worker node to run operating system package updates manually. Instead, apply VKE and node pool upgrades through Vultr and keep the platform declarative so workloads can be recreated from Git.

Because this low-cost setup points DNS directly to the public IP of the single worker node, a node replacement may change the public IP address. After a VKE or node pool upgrade, run:

```bash
cd infra
pulumi preview
pulumi up
```

Pulumi derives the current worker node public IP and updates the Vultr DNS apex `A` record when needed. The wildcard `CNAME` follows the apex record automatically.

## Naming convention

```text
<service>-<environment>-<sequence>
```

Examples:

- vke-prd-01

## Requirements

Before using this repository, ensure the following tools are installed.

### Required tools

- Python 3.10 or newer
- uv (Python package and virtual environment manager)
- Pulumi CLI
- Git
- (_Optional_) GitHub CLI (gh) for repository creation
- (_Optional_) vultr-cli for querying Kubernetes versions

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

Select the latest version (_recommended_) and update:

```bash
infra/Pulumi.prd.yaml
```

with:

```yaml
config:
  vultr-kubernetes-platform:kubernetes_version: v1.xx.x+1
```

## Initial setup

### Create Pulumi Configuration

`prd` is the Pulumi stack name chosen for the production instance of this small platform.

Copy the sample configuration:

```bash
cp Pulumi.sample.yaml Pulumi.prd.yaml
```

Edit `Pulumi.prd.yaml` and adjust the values for your environment.

### Initialize Pulumi Stack

If this is the first time using the project, create the stack:

```bash
cd infra
pulumi stack init prd
```

If the stack already exists, select it:

```bash
pulumi stack select prd
```

### Configure local secrets

The Pulumi program loads local secrets from:

```text
infra/secrets.local.env
```

This file is intentionally ignored by Git. A sample file is provided:

```text
infra/secrets.local.env.sample
```

Create the local file:

```bash
cp infra/secrets.local.env.sample infra/secrets.local.env
```

Then edit it and set at least:

```bash
VULTR_API_KEY="<VULTR_API_KEY>"
POSTGRESQL_SUPERUSER_PASSWORD="<POSTGRESQL_SUPERUSER_PASSWORD>"
POSTGRESQL_APP_PASSWORD="<POSTGRESQL_APP_PASSWORD>"
```

The Vultr API key is used for two purposes:

- by Pulumi to manage Vultr infrastructure, such as the VKE cluster and DNS records
- by cert-manager, through a Pulumi-created Kubernetes Secret, to complete Vultr DNS-01 challenges

The PostgreSQL passwords are used by Pulumi to create Kubernetes Secrets for the shared PostgreSQL platform database.

The Pulumi code creates an explicit Vultr provider from this value. This avoids storing the API key in `Pulumi.prd.yaml`, even in encrypted form.

Pulumi reads `infra/secrets.local.env` directly from Python. The file does not need to be sourced into the shell.

### Deploy infrastructure

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

Copy the generated kubeconfig to the standard Kubernetes location:

```bash
mkdir -p ~/.kube
cp kubeconfig.yaml ~/.kube/config
chmod 600 ~/.kube/config
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

### Cert-manager and TLS verification

Check cert-manager and issuer status:

```bash
kubectl get applications -n argocd
kubectl get pods -n cert-manager
kubectl get clusterissuer
```

Check certificates for an application namespace:

```bash
kubectl get certificate -n welcome
kubectl describe certificate welcome-example-com-tls -n welcome
```

The `welcome` test app should be reachable over HTTPS:

```bash
curl -v https://welcome.example.com/
```

Certificate renewal is handled by cert-manager at runtime. GitOps defines the desired `Ingress`, `Certificate`/TLS secret reference and `ClusterIssuer`; cert-manager monitors the certificate lifecycle and renews certificates before expiry as long as the issuer, DNS credentials and DNS-01 validation continue to work.

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
### Application database provisioning

Applications can declare database requirements through `infra/apps.yaml`.

Example:

```yaml
authentik:
  namespace: true
  database: true
  secret_requirements:
    - postgresql_password
    - secret_key
```

When `database: true` is specified, Pulumi automatically creates:

* A PostgreSQL login role
* A PostgreSQL database owned by that role
* A Kubernetes Secret containing the database credentials in the `platform-database` namespace

The role and database names are derived deterministically from the application name and domain name.

This allows new applications to obtain dedicated PostgreSQL resources through configuration rather than manual database administration.

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

#### Option 2: GitHub CLI (_recommended_)

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

### Argo CD health customization for Traefik Ingresses

This platform exposes Traefik through `hostPort` on a single worker node instead of through a Kubernetes `LoadBalancer` Service.

Because of this, Kubernetes `Ingress` resources do not receive a `status.loadBalancer.ingress` address. The Ingress can still route correctly through Traefik, but Argo CD may otherwise keep applications in `Progressing` health state.

To make Argo CD health match the chosen low-cost ingress architecture, the repository includes a partial Server-Side Apply patch for `argocd-cm`:

```text
platform/argocd/argocd-cm-ingress-health.yaml
```

This customization treats `Ingress` resources with `ingressClassName: traefik` as healthy without requiring a load balancer address.

If this configuration is changed, the Argo CD application controller may need to be restarted so it reloads `argocd-cm`:

```bash
kubectl rollout restart statefulset/argocd-application-controller -n argocd
kubectl rollout status statefulset/argocd-application-controller -n argocd
```
