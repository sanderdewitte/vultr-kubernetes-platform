# Platform

Kubernetes platform components managed by Argo CD.

This directory contains Argo CD `Application` manifests and related configuration for platform-level components.

## Components

| Component | Status | Purpose |
|---|---|---|
| Argo CD | Bootstrap | GitOps controller |
| Traefik | Active | Ingress controller |
| cert-manager | Planned | TLS certificate management |

## Notes

- Argo CD itself is installed by the bootstrap script.
- Platform components are managed via Argo CD Applications.
- Do not manually install platform components with `helm install` or `kubectl apply`, except for the bootstrap process.
