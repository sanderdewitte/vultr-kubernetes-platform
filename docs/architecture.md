# Architecture

## Overview

The platform is a small, low-cost Kubernetes environment on Vultr Kubernetes Engine.

Pulumi manages infrastructure and application prerequisites. Argo CD manages shared platform components and application deployments.

## Traffic flow

```text
Vultr DNS
  ↓
Single VKE worker node public IP
  ↓
Node host ports 80 and 443
  ↓
Traefik ingress controller
  ↓
Kubernetes Ingress
  ↓
ClusterIP Service
  ↓
Application Pods
```

Traefik is the only component exposed directly on the worker node.

Applications use `ClusterIP` Services and rely on Traefik for external access.

## Traefik port model

```text
Node port 80  → container port 8000
Node port 443 → container port 8443
```

The Traefik container listens on unprivileged ports while Kubernetes maps the public node ports through `hostPort`.

The chart configuration explicitly defines `exposedPort` values so redirects advertise public ports 80 and 443 rather than internal ports 8000 and 8443.

Because the platform has one worker node and Traefik uses host ports, Traefik uses a `Recreate` deployment strategy. This avoids blocked rolling updates when a replacement Pod cannot bind ports already in use by the existing Pod.

## DNS model

Pulumi manages Vultr DNS records.

```text
example.com      A      <VKE worker node public IP>
*.example.com    CNAME  example.com
```

Pulumi derives the current worker node public IP from the VKE node pool.

If the node is replaced and receives a new public IP address, `pulumi up` updates the apex record.

## Certificate model

cert-manager is installed as a platform component.

The platform uses Let's Encrypt with ACME DNS-01 validation through the Vultr webhook.

Two ClusterIssuers are provided:

```text
letsencrypt-staging
letsencrypt-production
```

Applications request certificates through Ingress annotations and TLS configuration.

The Vultr API token is stored outside Git and is written to Kubernetes by Pulumi.

## PostgreSQL model

CloudNativePG runs a shared PostgreSQL cluster.

Applications can request dedicated database resources through `apps/apps.yaml`.

For each application and domain combination, Pulumi can create:

- a PostgreSQL login role
- a database owned by that role
- a database credential Secret in the platform database namespace

## Application model

Applications are defined once in `apps/apps.yaml` and enabled per domain in `Pulumi.<stack>.yaml`.

Pulumi creates:

- namespaces
- Secrets
- database resources
- Argo CD Application resources

Argo CD then deploys the application from Git and, when applicable, an upstream Helm chart.

## Cost and availability trade-off

The platform intentionally avoids a managed load balancer.

This reduces monthly cost but means the ingress layer is not highly available.

If the single worker node is unavailable, external access to applications is unavailable.

The Pulumi configuration validates that this architecture is used with exactly one worker node.

## Resource naming

Resources are named programmatically according to the scope in which they must be unique.

### Cluster-wide resources

Resources that are cluster-wide or shared between applications must include sufficient context (such as application and domain) to guarantee uniqueness.

Examples:

- `authentik-example-com-postgresql`
- `homarr-example-com-postgresql`

### Namespace-local resources

Resources that are created inside an application namespace do not repeat the domain name. The namespace already provides uniqueness.

Examples:

Namespace:
`homarr-example-com`

Resources:
- `homarr-postgresql-url`
- `homarr-secret-encryption-key`

This keeps resource names concise and avoids repeating information already encoded in the namespace.

It also keeps programmatically generated resource names predictable and allows application-specific configuration files, such as Helm values files, to remain independent of deployment-specific details such as domains. A values file should describe how an application is configured, while domain-specific information should be provided by the deployment layer when resources are generated.
