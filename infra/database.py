import pulumi
import pulumi_kubernetes as k8s
from constants import PLATFORM_DATABASE_NAMESPACE, POSTGRESQL_CLUSTER_NAME


def create_postgresql_namespace(kubernetes_provider) -> k8s.core.v1.Namespace:

    return k8s.core.v1.Namespace(
        PLATFORM_DATABASE_NAMESPACE,
        metadata={
            "name": PLATFORM_DATABASE_NAMESPACE,
        },
        opts=pulumi.ResourceOptions(
            provider=kubernetes_provider,
        ),
    )


def create_postgresql_cluster(kubernetes_provider, namespace) -> k8s.apiextensions.CustomResource:

    cluster = k8s.apiextensions.CustomResource(
        POSTGRESQL_CLUSTER_NAME,
        api_version="postgresql.cnpg.io/v1",
        kind="Cluster",
        metadata={
            "name": POSTGRESQL_CLUSTER_NAME,
            "namespace": PLATFORM_DATABASE_NAMESPACE,
        },
        spec={
            "instances": 1,
            "superuserSecret": {
                "name": "postgresql-superuser",
            },
            "bootstrap": {
                "initdb": {
                    "database": "platform",
                    "owner": "platform",
                    "secret": {
                        "name": "postgresql-app",
                    },
                },
            },
            "storage": {
                "size": "5Gi",
            },
        },
        opts=pulumi.ResourceOptions(
            provider=kubernetes_provider,
            depends_on=[namespace],
        ),
    )

    return cluster