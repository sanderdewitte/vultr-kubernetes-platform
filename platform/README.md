# Platform

Kubernetes platform components managed by Argo CD.

This directory contains Argo CD `Application` manifests and related configuration for platform-level components.

## Components

| Component | Status | Purpose |
|---|---|---|
| Argo CD | Bootstrap | GitOps controller |
| Traefik | Active | Ingress controller |
| cert-manager | Active | TLS certificate management |
| cert-manager Vultr webhook | Active | Vultr integration for cert-manager |
| ClusterIssuers | Active | ACME and Let's Encrypt configuration |

## Notes

- Argo CD itself is installed by the bootstrap process.
- Platform components are managed declaratively via Argo CD Applications.
- cert-manager uses DNS-01 validation through the Vultr webhook.
- TLS certificates are automatically renewed by cert-manager.
- Do not manually install platform components with `helm install` or `kubectl apply`, except during bootstrap.
