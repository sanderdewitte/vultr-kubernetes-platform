# Infrastructure

Pulumi-based infrastructure for Vultr Kubernetes Engine.

## Usage

```bash
cd infra
uv run pulumi preview
uv run pulumi up
```

## Notes

- Uses Python + uv
- Requires Vultr API key via Pulumi config or environment variable
