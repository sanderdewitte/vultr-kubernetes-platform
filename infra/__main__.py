#!/usr/bin/env python3
"""
Pulumi entrypoint for the Vultr Kubernetes platform.

This file orchestrates resource creation by calling
the individual modules (config, cluster, outputs).
"""

# Imports
from config import Settings
from cluster import create_cluster
from outputs import export_outputs

# Configuration
settings = Settings()

# Resources
cluster = create_cluster(settings)

# Outputs
export_outputs(cluster)