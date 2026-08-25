# Applications

## Overview

Applications are defined centrally in the application catalog:

```text
apps/apps.yaml
```

The catalog describes the reusable capabilities and deployment requirements of each supported application.

Domains select applications in the Pulumi stack configuration:

```text
infra/Pulumi.<stack>.yaml
```

This separates two concerns:

- `apps/apps.yaml` defines what an application needs and how Pulumi can configure its Helm chart.
- `Pulumi.<stack>.yaml` defines which applications are deployed for each domain and any domain-specific deployment configuration.

Application-specific Helm values remain under:

```text
apps/<application>/values.yaml
```

Where comparable, application's `values.yaml` files should use a consistent section order to improve readability:

1. scaling and workload configuration
2. environment and application configuration
3. database and external services
4. secrets
5. service
6. ingress
7. persistence and storage
8. resources

This ordering is guidance rather than a strict schema. Upstream chart structure and application-specific requirements take precedence.

Pulumi generates deployment-specific values such as hostnames, TLS Secret names, database identifiers and OpenID Connect (OIDC) settings.
Argo CD deploys the application from its upstream Helm chart together with the values stored in Git.

## Application catalog model

A catalog entry can describe:

- whether the application requires a dedicated namespace
- database requirements
- Helm chart repository and version
- (default) hostname prefix
- application Secret requirements
- Helm parameter paths populated by Pulumi
- optional OIDC authentication support

For example, a simplified database-backed application could be defined as:

```yaml
example_app:
  namespace: true
  database:
    enabled: true
    connection_url_secret: true
  chart:
    repository_url: https://example.com/charts/
    version: 1.2.3
  default_host_prefix: app
  secret_requirements:
    - postgresql_password
    - encryption_key
  helm_parameter_paths:
    ingress_host: ingress.hosts[?].host
    ingress_tls_secret: ingress.tls[?].secretName
    ingress_tls_host: ingress.tls[?].hosts[?]
```

Application identifiers (in the example above: `example_app`) are explained in more detail in section [Domain application entries](#domain-application-entries) below.
The `[?]` placeholders represent Helm list indexes and are explained in more detail in section [Helm parameter paths](#helm-parameter-paths) below.

## Namespace

Set:

```yaml
namespace: true
```

when the application should have a dedicated namespace.

The namespace name is derived from the application and domain, for example:

```text
homarr-example-com
```

A dedicated namespace is required when the application defines application Secret requirements or requests a database connection URL Secret.

## Hostname

Every application defines a default hostname prefix:

```yaml
default_host_prefix: www
```

Combined with a domain, this produces a hostname such as:

```text
www.example.com
```

A domain deployment can override the default:

```yaml
applications:
  - example_app:
      host_prefix: dashboard
```

which would produce:

```text
dashboard.example.com
```

DNS for application hostnames is managed automatically by Pulumi according to the domain's DNS configuration.

## Database support

An application that requires PostgreSQL declares:

```yaml
database:
  enabled: true
```

For every enabled domain/application combination, Pulumi creates a dedicated PostgreSQL role, database and password Secret.

The database and role names are derived from the application and domain, for example:

```text
homarr_example_com
```

The PostgreSQL cluster itself is shared platform infrastructure, while each application/domain deployment has its own database identity and credentials.

### Connection URL Secret

Some applications expect a complete PostgreSQL connection URL rather than separate connection parameters.

Such an application can request:

```yaml
database:
  enabled: true
  connection_url_secret: true
```

Pulumi then creates an additional Secret in the application's namespace containing a `url` key with the complete PostgreSQL connection URL.

For example:

```text
Secret:
homarr-postgresql-url

Key:
url
```

`connection_url_secret` can only be enabled when both the database and application namespace are enabled.

## Application Secrets

Application-specific Secret requirements are declared as identifiers:

```yaml
secret_requirements:
  - postgresql_password
  - encryption_key
```

For every configured domain, the corresponding values are read from environment variables using the application, domain and Secret identifiers.

For example, a requirement such as:

```text
secret_encryption_key
```

for Homarr on `example.com` is represented by an environment variable following the platform's domain/application Secret naming convention.

Secret values are not stored in `apps/apps.yaml`, `values.yaml`, nor in the Pulumi stack configuration.

The required values should be provided through `infra/secrets.local.env` or directly in the environment.

Application Secret requirements require a dedicated application namespace.

## Helm parameter paths

The application catalog tells Pulumi where generated deployment-specific values belong in the upstream Helm chart.

For example:

```yaml
helm_parameter_paths:
  ingress_host: ingress.hosts[?].host
  ingress_tls_secret: ingress.tls[?].secretName
  ingress_tls_host: ingress.tls[?].hosts[?]
```

Pulumi replaces the `?` placeholders with the required Helm list indexes and supplies the generated values to the Argo CD `Application`.

Supported generated parameters include values for:

- database identifiers
- ingress hostname
- ingress TLS Secret
- ingress TLS hostname
- OIDC configuration

Ingress parameter paths form a complete set: when ingress parameter generation is used, all required ingress paths must be defined.

Database identifier parameter paths can only be configured when database support is enabled.

This mechanism keeps deployment-specific values out of `apps/<application>/values.yaml`.

## OIDC authentication

An application can declare support for OIDC in the catalog.

For example:

```yaml
authentication:
  oidc:
    display_name: SSO
    secret_requirements:
      - client_id
      - client_secret
    helm_parameter_paths:
      providers: env.AUTH_PROVIDERS
      issuer: env.AUTH_OIDC_ISSUER
      client_name: env.AUTH_OIDC_CLIENT_NAME
      scope: env.AUTH_OIDC_SCOPE_OVERWRITE
      groups_attribute: env.AUTH_OIDC_GROUPS_ATTRIBUTE
      logout_redirect_url: env.AUTH_LOGOUT_REDIRECT_URL
```

The OIDC Secret requirements are fixed to:

```text
client_id
client_secret
```

The corresponding credentials are stored as a Secret in the application's namespace.

`display_name` is optional. When present, it controls the provider name presented by the application, such as `SSO`.
When omitted, the display name is derived from the identity provider application identifier.

The Helm parameter paths tell Pulumi where the generated OIDC values belong in the application's Helm chart.

## Enabling OIDC for a domain deployment

Catalog support does not enable OIDC automatically.

OIDC is enabled for an individual application deployment in `Pulumi.<stack>.yaml`:

```yaml
config:
  vultr-kubernetes-platform:domains:
    - name: example.com
      apex: true
      wildcard: true
      applications:
        - authentik
        - homarr:
            authentication:
              oidc:
                identity_provider: authentik
```

The identity provider must:

- be present in the application catalog
- support the expected provider endpoint
- normally be deployed for the same domain

For the configuration above, Pulumi derives values such as:

```text
Homarr:
www.example.com

Authentik:
auth.example.com

OIDC issuer:
https://auth.example.com/application/o/homarr/
```

Pulumi also generates the logout endpoint and standard OIDC parameters expected by the application.

The OIDC client itself must be configured in the identity provider with matching credentials and redirect URIs.
Authorization policy remains an identity-provider/application concern rather than being inferred merely from the presence of a user account.

## Domain application entries

Applications can be enabled in a domain using their identifier:

```yaml
applications:
  - authentik
```

Application identifiers must use lowercase letters, digits and underscores and must start with a lowercase letter.
A single string list item as above, without any further specifications, uses the defaults from the application catalog.

When deployment-specific configuration is needed, use a single-key mapping:

```yaml
applications:
  - homarr:
      authentication:
        oidc:
          identity_provider: authentik
```

The deployment configuration is recursively merged with the application's catalog configuration.

This allows a domain to override supported deployment settings without duplicating the complete catalog entry.

Currently supported domain deployment configuration includes:

- `host_prefix`
- `authentication.oidc.identity_provider`

## Current application catalog

For the applications currently supported by the platform and their application-specific configuration, see [Application catalog](application-catalog.md).

## Adding an application

Adding a new application generally consists of the following steps:

1. Add an application definition to `apps/apps.yaml`.
2. Create `apps/<application>/values.yaml` containing reusable Helm values.
3. Add any required Secret variables to `infra/secrets.local.env`.
4. Add the application to the appropriate domain in `Pulumi.<stack>.yaml`.
5. Run `pulumi preview --diff` and review the generated resources and Helm parameters.
6. Run `pulumi up`.
7. Verify the Argo CD `Application` and resulting Kubernetes resources.
8. Commit and push the configuration so Git and the deployed Argo CD revision agree.

If OIDC authentication is enabled, also configure the corresponding provider/application in the domain's identity provider and ensure its client credentials match the platform Secret values.

## Validation

The platform performs configuration validation before creating resources.

Among other checks, it validates:

- application identifier format
- supported catalog and deployment keys
- required hostname prefixes
- Secret requirement structure and presence
- namespace requirements for application Secrets
- database configuration consistency
- database connection URL prerequisites
- OIDC support and required client credentials
- OIDC identity provider references
- Helm parameter path completeness and placeholder counts
- database and ingress parameter dependencies

Configuration errors are reported with their scope and, where possible, a corrective hint.

This validation is intended to catch invalid application definitions and domain deployment configuration before Pulumi attempts to change the platform.
