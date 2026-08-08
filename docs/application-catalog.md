# Current applications

The current application catalog contains:

- Authentik
- Homarr

Application definitions are stored in `apps/apps.yaml`.
For the generic application model and deployment configuration, see [Applications](applications.md).

## Authentik

Authentik is deployed per domain and provides identity services for applications on that domain.

Current configuration:

- Helm chart repository: `https://charts.goauthentik.io`
- Helm chart version: `2026.5.3`
- default hostname prefix: `auth`
- dedicated namespace
- dedicated PostgreSQL database
- PostgreSQL password and Authentik secret key
- generated database and ingress Helm parameters

## Homarr

Homarr is deployed as the `www` application and is the first application using the platform's generic OpenID Connect (OIDC) integration.

Current configuration:

- Helm chart repository: `https://homarr-labs.github.io/charts/`
- Helm chart version: `8.25.0`
- default hostname prefix: `www`
- dedicated namespace
- dedicated PostgreSQL database
- namespace-local PostgreSQL connection URL Secret
- encryption key
- generated ingress parameters
- OIDC support with domain-specific client credentials
- `SSO` as the configured OIDC display name