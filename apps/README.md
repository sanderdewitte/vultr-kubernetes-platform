# Applications

Kubernetes applications deployed via Argo CD.

Each application should be defined declaratively and committed to this repository.

## Notes

- Applications should use Kubernetes namespaces for isolation.
- Applications exposed externally should use Traefik Ingress resources.
- TLS certificates should be managed through cert-manager ClusterIssuers.
- Application configuration should remain GitOps-managed.
