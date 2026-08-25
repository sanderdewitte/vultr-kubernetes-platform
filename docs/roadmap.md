# Roadmap

## Near term

- Deploy a Wagtail CMS website and validate multi-domain behavior end-to-end
- Add WebDAV as an application using plain Kubernetes manifests and validate the non-Helm application deployment path
- Publish selected management interfaces through Traefik
- Configure PostgreSQL backups
- Add an automatic pre-migration PostgreSQL backup before Wagtail database migrations during application deployment
- Document backup restore testing
- Add automated tests for configuration validation and helper logic
- Add integration-style tests for generated application configuration

## Later

- Add metrics-server
- Add manually triggered GitHub Actions for Pulumi preview
- Optionally add approved Pulumi up workflow
- Make the configured repository URL the single source of truth for Argo CD platform Applications
