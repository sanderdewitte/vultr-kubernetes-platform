# Vultr Kubernetes Platform

A small, reproducible and cost-conscious Kubernetes platform built on Vultr Kubernetes Engine (VKE), using Pulumi for infrastructure provisioning and Argo CD for GitOps deployment.

The platform is designed to remain understandable after periods of inactivity, while still following secure-by-default practices and established open-source patterns.

It supports hosting multiple independent domains, each with its own selection of applications, namespaces, secrets, databases and ingress configuration, while sharing a common Kubernetes platform.

## Goals and design principles

- Deploy a small managed Kubernetes cluster on Vultr Kubernetes Engine (VKE).
- Cost-conscious architecture, keep monthly costs low.
- Infrastructure as Code for Vultr resources and application prerequisites.
- GitOps for platform components and applications.
- Avoid unnecessary managed services unless they clearly reduce maintenance.
- Prefer secure-by-default configurations and well-established open-source technologies.
- Keep the repository structure readable and predictable.
- Application deployments driven by configuration rather than manual steps.
- Support multiple domains, each with its own configurable set of applications.

## Architecture at a glance

This platform is designed as a small, low-cost GitOps-managed Kubernetes environment on Vultr Kubernetes Engine (VKE).

The platform intentionally avoids a managed Vultr Load Balancer. Instead, public traffic enters the cluster through the public IP address of a single VKE worker node.

This single-node architecture is an intentional design choice. It keeps the platform inexpensive and easy to understand while still providing a realistic Kubernetes environment for self-hosting. If the platform later grows beyond a single worker node, the ingress architecture can be revisited.

```text
           GitHub
             │
             ▼
          Argo CD
             │
             ▼
   ┌───────────────────┐
   │ Kubernetes        │
   │ ├── Traefik       │
   │ ├── cert-manager  │
   │ ├── CloudNativePG │
   │ └── Applications  │
   └───────────────────┘
             ▲
             │
           Pulumi
           ├── VKE cluster
           ├── Vultr DNS
           ├── Namespaces
           ├── Secrets
           └── PostgreSQL
```

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

## Platform components

The platform currently includes:

| Component | Purpose | Notes |
|-----------|---------|-------|
| Vultr Kubernetes Engine (VKE) | Managed Kubernetes cluster | Single worker node by design |
| Pulumi | Infrastructure as Code | Manages Vultr and Kubernetes prerequisites |
| Vultr DNS | DNS hosting | Public DNS records |
| Argo CD | GitOps | Continuously reconciles Git with Kubernetes |
| Traefik | Ingress controller | HTTP/HTTPS entry point |
| Cert-Manager | Certificate management | Automates TLS certificates |
| Cert-Manager Vultr webhook | DNS-01 validation | Integrates cert-manager with Vultr DNS |
| Let's Encrypt | Certificate authority | Issues public TLS certificates |
| CloudNativePG | PostgreSQL operator | Runs the shared PostgreSQL cluster |
| Shared PostgreSQL platform database | Database service | Shared by applications that need a database |
| Automatic PostgreSQL provisioning | Database automation | Creates application roles and databases |
| Application-driven Argo CD generation | Deployment automation | Pulumi generates Argo CD Applications |

## Multi-domain application model

The platform is designed to host multiple independent domains on a shared Kubernetes cluster.

Each domain can enable its own set of applications through configuration in `Pulumi.prd.yaml`:

```yaml
config:
  vultr-kubernetes-platform:domains:
    - name: example.com
      applications:
        - authentik
        - homarr
    - name: example.org
      applications:
        - drupal
```

Pulumi automatically provisions the required namespaces, secrets, databases and Argo CD Applications for the selected applications.

Applications therefore become a configuration choice rather than a deployment task.

## Applications

Currently implemented or planned:

| Application | Purpose | Suggested host prefix | Status |
|-------------|---------|-----------------------|--------|
| Authentik | Identity provider (SSO) | `auth` | ✅ Implemented |
| Homarr | Homepage and application dashboard | `www` | 🔄 In progress |
| Drupal | Website CMS | `www` | 📋 Planned |

## Repository layout

```text
.
├── apps/
│   └── authentik/
│       └── values.yaml
├── docs/
├── infra/
│   ├── apps.py
│   ├── apps.yaml
│   ├── config.py
│   ├── database.py
│   ├── secure.py
│   └── Pulumi.<stack>.yaml
├── platform/
│   ├── argocd/
│   ├── cert-manager/
│   ├── cloudnative-pg/
│   └── traefik/
└── scripts/
```

`infra/` contains the Pulumi program and application metadata.

`platform/` contains shared cluster services managed by Argo CD.

`apps/` contains application-specific Helm values and, when needed, Kubernetes manifests.

## Documentation

- [Architecture](docs/architecture.md)
- [Installation](docs/installation.md)
- [GitOps](docs/gitops.md)
- [Applications](docs/applications.md)
- [Operations](docs/operations.md)
- [Security](docs/security.md)
- [Roadmap](docs/roadmap.md)

## Prerequisites

Before following the Quick start below, ensure the following (required) tools are installed:

| Tool | Requirement | Purpose |
|------|-------------|---------|
| Python 3.10 or newer | ✅ Required | Required to run the Pulumi program. |
| uv | ✅ Required | Python package, virtual environment and project manager. |
| Pulumi CLI | ✅ Required | Provisions the infrastructure and Kubernetes resources. |
| kubectl | ✅ Required | Kubernetes command-line client. |
| Git | ✅ Required | Version control and GitOps workflow. |
| GitHub CLI (`gh`) | 💡 Optional | Convenient GitHub repository management. |
| vultr-cli | 💡 Optional | Optional management of Vultr resources. |

Detailed installation instructions are available in the documentation linked above.

## Quick start

1. Clone this repository.

   ```text
   Clone this repository to your local machine.
   ```

2. Create your own GitHub repository (or fork this one).

   ```text
   Push this project to your own GitHub repository.
   The repository URL will be used in Pulumi.prd.yaml.
   ```

3. Copy the sample Pulumi configuration:

   ```bash
   cd infra
   cp Pulumi.sample.yaml Pulumi.prd.yaml
   ```

4. Create the local secrets file:

   ```bash
   cp secrets.local.env.sample secrets.local.env
   ```

5. Configure the Pulumi stack and local secrets:

   ```text
   Edit:
   - Pulumi.prd.yaml
   - secrets.local.env
   Set repository_url to your own GitHub repository.
   ```

6. Deploy infrastructure:

   ```bash
   pulumi stack select prd
   pulumi preview
   pulumi up
   ```

7. Retrieve and install the kubeconfig:

   ```bash
   pulumi stack output kubeconfig --show-secrets | base64 -d > kubeconfig.yaml
   mkdir -p ~/.kube
   cp kubeconfig.yaml ~/.kube/config
   chmod 600 ~/.kube/config
   kubectl get nodes
   ```

8. Commit and push the repository to GitHub:

   ```bash
   git add .
   git commit -m "Initial platform configuration"
   git push
   ```

9. Bootstrap Argo CD and enable GitOps:

   ```bash
   ./scripts/shell/bootstrap-argocd.sh --bootstrap-root-app
   ```

Detailed procedures are available in the documentation linked above.

## Current status

The platform is operational and has successfully deployed its first real application, Authentik, including:

- dedicated namespace
- application Secrets
- PostgreSQL role and database
- Argo CD multi-source Application
- upstream Helm chart
- Traefik Ingress
- automatic Let's Encrypt certificate
- platform-wide HTTP-to-HTTPS redirect
