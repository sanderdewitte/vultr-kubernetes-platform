import pulumi
import pulumi_kubernetes as k8s

from constants import PLATFORM_DATABASE_NAMESPACE, POSTGRESQL_CLUSTER_NAME, POSTGRESQL_CNPG_API_VERSION
from app_naming import get_domain_application_database_identifier, get_domain_application_database_secret_name


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


def create_postgresql_cluster(settings, kubernetes_provider, namespace, postgresql_superuser_secret, postgresql_app_secret) -> k8s.apiextensions.CustomResource:

    cluster = k8s.apiextensions.CustomResource(
        POSTGRESQL_CLUSTER_NAME,
        api_version=POSTGRESQL_CNPG_API_VERSION,
        kind="Cluster",
        metadata={
            "name": POSTGRESQL_CLUSTER_NAME,
            "namespace": PLATFORM_DATABASE_NAMESPACE,
        },
        spec={
            "instances": 1,
            "superuserSecret": {
                "name": postgresql_superuser_secret.metadata["name"],
            },
            "managed": {
                "roles": get_domain_application_database_roles(settings),
            },
            "bootstrap": {
                "initdb": {
                    "database": "platform",
                    "owner": "platform",
                    "secret": {
                        "name": postgresql_app_secret.metadata["name"],
                    },
                },
            },
            "storage": {
                "size": "5Gi",
            },
        },
        opts=pulumi.ResourceOptions(
            provider=kubernetes_provider,
            depends_on=[
                namespace,
                postgresql_superuser_secret,
                postgresql_app_secret,
            ],
        ),
    )

    return cluster

def get_domain_application_database_roles(settings) -> list[dict]:

    managed_roles = []

    for domain in settings.domains:

        domain_name = domain["name"]

        for domain_application, application_config in settings.domain_applications(domain_name).items():

            if not application_config.get("database", False):
                continue

            database_identifier = get_domain_application_database_identifier(
                settings=settings,
                application=domain_application,
                domain_name=domain_name,
            )

            database_secret_name = get_domain_application_database_secret_name(
                settings=settings,
                application=domain_application,
                domain_name=domain_name,
            )

            managed_roles.append(
                {
                    "name": database_identifier,
                    "ensure": "present",
                    "login": True,
                    "superuser": False,
                    "passwordSecret": {
                        "name": database_secret_name,
                    },
                }
            )

    return managed_roles


def create_domain_application_databases(settings, kubernetes_provider, postgresql_cluster) -> dict[str, k8s.apiextensions.CustomResource]:

    databases = {}

    for domain in settings.domains:

        domain_name = domain["name"]

        for domain_application, application_config in settings.domain_applications(domain_name).items():

            if not application_config.get("database", False):
                continue

            database_identifier = get_domain_application_database_identifier(
                settings=settings,
                application=domain_application,
                domain_name=domain_name,
            )

            database_resource_name = settings.identifier_to_slug(database_identifier)

            databases[database_resource_name] = k8s.apiextensions.CustomResource(
                database_resource_name,
                api_version=POSTGRESQL_CNPG_API_VERSION,
                kind="Database",
                metadata={
                    "name": database_resource_name,
                    "namespace": PLATFORM_DATABASE_NAMESPACE,
                },
                spec={
                    "name": database_identifier,
                    "owner": database_identifier,
                    "cluster": {
                        "name": POSTGRESQL_CLUSTER_NAME,
                    },
                },
                opts=pulumi.ResourceOptions(
                    provider=kubernetes_provider,
                    depends_on=[postgresql_cluster],
                ),
            )

    return databases