# Infrastructure

Pulumi-based infrastructure for the Vultr Kubernetes platform.

This directory manages the underlying infrastructure required for the Kubernetes platform, including:

- Vultr Kubernetes Engine (VKE)
- Worker node discovery
- DNS records
- Kubernetes provider configuration
- Kubernetes Secrets required by platform components

## Usage

Install/sync Python dependencies:

```bash
cd infra
uv sync
```

Run Pulumi using the Pulumi CLI:

```bash
pulumi preview
pulumi up
```

## Notes

- Uses Python + uv
- Uses explicit Pulumi providers for Vultr and Kubernetes
- The Pulumi CLI must be installed separately, it is not provided by uv
- Supports multiple domains
- Reads sensitive local configuration from `infra/secrets.local.env`
- `infra/secrets.local.env` must not be committed to Git
- `infra/secrets.local.env.sample` contains example variables
