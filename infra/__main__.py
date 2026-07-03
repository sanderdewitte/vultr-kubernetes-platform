#!/usr/bin/env python3
"""
Pulumi entrypoint for the Vultr Kubernetes platform.

This file orchestrates resource creation by calling individual modules
for configuration, providers, the Kubernetes cluster, worker node lookup,
DNS, secrets, the platform database, domain application databases,
Argo CD application definitions and outputs.
"""

# Imports
from config import Settings
from providers import create_vultr_provider, create_kubernetes_provider
from cluster import create_cluster
from worker_node import get_first_worker_public_ip
from dns import create_dns_records
from secure import create_kubernetes_secrets
from constants import POSTGRESQL_SUPERUSER_SECRET_KEY, POSTGRESQL_APP_SECRET_KEY
from database import create_postgresql_namespace, create_postgresql_cluster, create_domain_application_databases
from apps import create_domain_application_argocd_applications
from outputs import export_outputs

# Configuration
settings = Settings()

# Infrastructure provider
vultr_provider = create_vultr_provider(settings)

# Kubernetes cluster
cluster = create_cluster(settings, vultr_provider)
kubernetes_provider = create_kubernetes_provider(cluster)
platform_ip = get_first_worker_public_ip(cluster, vultr_provider)

# DNS
dns_records = create_dns_records(settings, platform_ip, vultr_provider)

# Secrets
kubernetes_secrets = create_kubernetes_secrets(settings, kubernetes_provider)

# PostgreSQL platform database cluster
postgresql_namespace = create_postgresql_namespace(kubernetes_provider)
postgresql_cluster = create_postgresql_cluster(
    settings=settings,
    kubernetes_provider=kubernetes_provider,
    namespace=postgresql_namespace,
    postgresql_superuser_secret=kubernetes_secrets[POSTGRESQL_SUPERUSER_SECRET_KEY],
    postgresql_app_secret=kubernetes_secrets[POSTGRESQL_APP_SECRET_KEY],
)
domain_application_databases = create_domain_application_databases(
    settings=settings,
    kubernetes_provider=kubernetes_provider,
    postgresql_cluster=postgresql_cluster,
)

# Domain application Argo CD Applications
domain_application_argocd_applications = create_domain_application_argocd_applications(
    settings=settings,
    kubernetes_provider=kubernetes_provider,
    domain_application_namespaces=kubernetes_secrets["domain_application_namespaces"],
)

# Outputs
export_outputs(cluster, platform_ip, dns_records)