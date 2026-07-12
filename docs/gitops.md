# GitOps

## Deployment model

```text
GitHub repository
├── infra/
├── platform/
└── apps/
```

Pulumi and Argo CD have separate responsibilities.

## Pulumi responsibilities

Pulumi manages:

- VKE
- Vultr DNS
- Kubernetes namespaces
- platform and application Secrets
- PostgreSQL roles and databases
- Argo CD Application resources

## Argo CD responsibilities

Argo CD manages:

- shared platform components
- Helm-based applications
- applications defined through Kubernetes manifests
- continuous reconciliation with Git

## Platform components

The root Argo CD Application watches `platform/`.

Examples:

- Traefik
- cert-manager
- cert-manager Vultr webhook
- CloudNativePG

## Application deployment

Pulumi creates domain-aware Argo CD Application resources.

For Helm applications, Argo CD uses multiple sources:

1. the upstream Helm chart repository
2. this Git repository for `values.yaml`

## Workflow

### Infrastructure change

```text
Edit infra/
  ↓
pulumi preview
  ↓
pulumi up
```

### Platform change

```text
Edit platform/
  ↓
Commit and push
  ↓
Argo CD reconciles
```

### Application change

```text
Edit apps/ or infra/apps.yaml
  ↓
Commit and push
  ↓
Run pulumi up when infrastructure resources change
  ↓
Argo CD reconciles
```

Argo CD reads the remote repository, not the local working tree.

## Verify the synced revision

For a multi-source Application:

```bash
git rev-parse --short HEAD

kubectl get application traefik -n argocd   -o jsonpath='{.status.sync.revisions[1]}' | cut -c1-7
echo
```

The values should match after reconciliation.
