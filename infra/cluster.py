import pulumi
import ediri_vultr as vultr

def create_cluster(settings, vultr_provider):

    return vultr.Kubernetes(
        settings.cluster_name,
        region=settings.region,
        label=settings.cluster_name,
        version=settings.kubernetes_version,
        node_pools={
            "label": "default",
            "node_quantity": settings.worker_node_count,
            "plan": settings.worker_node_plan,
        },
        opts=pulumi.ResourceOptions(provider=vultr_provider),
    )