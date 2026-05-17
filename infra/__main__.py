#!/usr/bin/env python3
"""
Pulumi entrypoint for the Vultr Kubernetes platform.

This file orchestrates resource creation by calling the
individual modules (config, cluster, worker_node, dns, outputs).
"""

# Imports
from config import Settings
from provider import create_vultr_provider
from cluster import create_cluster
from worker_node import get_first_worker_public_ip
from dns import create_dns_records
from outputs import export_outputs

# Configuration
settings = Settings()

# Resources
vultr_provider = create_vultr_provider(settings)
cluster = create_cluster(settings, vultr_provider)
platform_ip = get_first_worker_public_ip(cluster, vultr_provider)
dns_records = create_dns_records(settings, platform_ip, vultr_provider)

# Outputs
export_outputs(cluster, platform_ip, dns_records)