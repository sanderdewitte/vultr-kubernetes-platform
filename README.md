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

| Component                             | Purpose                    | Notes                                       |
| ------------------------------------- | -------------------------- | ------------------------------------------- |
| Vultr Kubernetes Engine (VKE)         | Managed Kubernetes cluster | Single worker node by design                |
| Pulumi                                | Infrastructure as Code     | Manages Vultr and Kubernetes prerequisites  |
| Vultr DNS                             | DNS hosting                | Public DNS records                          |
| Argo CD                               | GitOps                     | Continuously reconciles Git with Kubernetes |
| Traefik                               | Ingress controller         | HTTP/HTTPS entry point                      |
| Cert-Manager                          | Certificate management     | Automates TLS certificates                  |
| Cert-Manager Vultr webhook            | DNS-01 validation          | Integrates cert-manager with Vultr DNS      |
| Let's Encrypt                         | Certificate authority      | Issues public TLS certificates              |
| CloudNativePG                         | PostgreSQL operator        | Runs the shared PostgreSQL cluster          |
| Shared PostgreSQL platform database   | Database service           | Shared by applications that need a database |
| Automatic PostgreSQL provisioning     | Database automation        | Creates application roles and databases     |
| Application-driven Argo CD generation | Deployment automation      | Pulumi generates Argo CD Applications       |

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

| Application    | Purpose                            | Suggested host prefix | Deployment method           | Status         |
| -------------- | ---------------------------------- | --------------------- | --------------------------- | -------------- |
| Authentik      | Identity provider (SSO)            | `auth`                | Remote Helm chart           | ✅ Implemented |
| Homarr         | Homepage and application dashboard | `www`                 | Remote Helm chart           | ✅ Implemented |
| Wagtail        | Website CMS                        | `www`                 | Local Helm chart            | ✅ Implemented |
| WebDAV         | File synchronization               | `webdav`              | Direct Kubernetes resources | 🔄 In progress |
| Metrics Server | Container resource metrics for k8s | `monitor`             | Remote Helm chart           | 📋 Planned     |

Applications can be deployed using one of three methods:

- **Remote Helm chart** — an upstream Helm chart retrieved from a configured Helm repository.
- **Local Helm chart** — a Helm chart maintained as part of this repository, for applications requiring platform-specific deployment logic.
- **Direct Kubernetes resources** — Kubernetes resources managed directly by Pulumi without using Helm.

## Repository layout

```text
.
├── apps/
│   ├── apps.yaml
│   ├── authentik/
│   │   └── values.yaml
│   └── homarr/
│       └── values.yaml
├── infra/
│   ├── apps.py
│   ├── config.py
│   ├── database.py
│   ├── secure.py
│   └── Pulumi.<stack>.yaml
├── platform/
│   ├── argocd/
│   ├── cert-manager/
│   ├── cloudnative-pg/
│   └── traefik/
├── docs/
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

| Tool                 | Requirement | Purpose                                                  |
| -------------------- | ----------- | -------------------------------------------------------- |
| Python 3.10 or newer | ✅ Required  | Required to run the Pulumi program.                      |
| uv                   | ✅ Required  | Python package, virtual environment and project manager. |
| Pulumi CLI           | ✅ Required  | Provisions the infrastructure and Kubernetes resources.  |
| kubectl              | ✅ Required  | Kubernetes command-line client.                          |
| Git                  | ✅ Required  | Version control and GitOps workflow.                     |
| GitHub CLI (`gh`)    | 💡 Optional | Convenient GitHub repository management.                 |
| vultr-cli            | 💡 Optional | Optional management of Vultr resources.                  |

Detailed installation instructions are available in the documentation linked above.

## Quick start

The following is a condensed installation sequence. See [Installation](docs/installation.md) for the complete procedure and explanations.

1. Clone this repository and create your own GitHub repository (or fork this one).

   Push the project to your own GitHub repository. Its URL is used in the Pulumi configuration and by Argo CD.

2. Create the Pulumi configuration and local secrets file:

   ```bash
   cd infra
   cp Pulumi.sample.yaml Pulumi.prd.yaml
   cp secrets.local.env.sample secrets.local.env
   ```

   Configure `Pulumi.prd.yaml`, including `repository_url`, and set the required values in `secrets.local.env`.

3. Initialize or select the Pulumi stack:

   ```bash
   pulumi stack init prd
   ```

   For an existing stack, use `pulumi stack select prd` instead.

4. Temporarily enable bootstrap mode in `Pulumi.prd.yaml`:

   ```yaml
   vultr-kubernetes-platform:bootstrap: true
   ```

   For confirmation, set the following environment variable for the initial deployment:

   ```bash
   export VULTR_KUBERNETES_PLATFORM_BOOTSTRAP_CONFIRM=true
   ```

5. Deploy the bootstrap infrastructure:

   ```bash
   pulumi preview
   pulumi up
   unset VULTR_KUBERNETES_PLATFORM_BOOTSTRAP_CONFIRM
   ```

6. Retrieve and install the kubeconfig:

   ```bash
   pulumi stack output kubeconfig --show-secrets | base64 -d > kubeconfig.yaml
   chmod 600 kubeconfig.yaml
   mkdir -p ~/.kube
   cp kubeconfig.yaml ~/.kube/config
   chmod 600 ~/.kube/config
   kubectl get nodes
   ```

7. Return to the repository root and bootstrap Argo CD and the root Application:

   ```bash
   cd ..
   ./scripts/shell/bootstrap-argocd.sh --bootstrap-root-app
   ```

8. Allow Argo CD to reconcile the platform components and verify the bootstrap:

   ```bash
   kubectl get applications -n argocd
   ./scripts/shell/argocd-git-revision-check.sh --all
   ```

   Wait until the platform applications are `Synced` and `Healthy` before continuing.

9. Complete the platform deployment.

   Remove the temporary `vultr-kubernetes-platform:bootstrap: true` setting from `infra/Pulumi.prd.yaml`, ensure the required PostgreSQL and application-specific secrets are configured, then run:

   ```bash
   cd infra
   pulumi preview
   pulumi up
   ```

   If a platform prerequisite is still reconciling and the Pulumi deployment fails, wait for Argo CD to complete the relevant deployment and run `pulumi up` again.

## License

This project is licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE).


Unless otherwise indicated, all code authored by the project owner, including code committed before the addition of the `LICENSE` file, is made available under the Apache License, Version 2.0.

See [NOTICE](NOTICE) for copyright information.
