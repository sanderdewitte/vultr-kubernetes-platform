# Security

## Secret handling

Secrets are never stored in Git.

Pulumi loads secrets from:

```text
infra/secrets.local.env
```

The file is ignored by Git.

Pulumi writes required values to Kubernetes Secrets.

## Application Secrets

Application Secrets are namespace-local.

Different domains can therefore use identical Kubernetes Secret names while remaining isolated in separate namespaces.

## TLS

cert-manager automates certificate issuance and renewal through Let's Encrypt DNS-01 validation.

The Vultr API token is stored in a Kubernetes Secret with narrowly scoped access for the Vultr webhook.

## Traefik

Traefik runs with:

- no privilege escalation
- all Linux capabilities dropped
- read-only root filesystem
- unprivileged internal ports

Public node ports 80 and 443 are mapped to container ports 8000 and 8443.

HTTP is redirected to HTTPS platform-wide.

## Single-node trade-off

The platform does not provide ingress high availability.

Traefik uses `Recreate` because only one Pod can bind the host ports on the single worker node.

This creates a brief ingress interruption during Traefik updates.

## Future hardening

Potential improvements:

- shared Traefik security-header middleware
- removal of unnecessary product-identifying response headers
- NetworkPolicies
- PodDisruptionBudgets where applicable
- secret rotation procedures
- PostgreSQL backup and restore procedures
